#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
地理编码命令行工具

支持：
  - 结构化输入（places_structured.json 格式，自动提取 places 数组）
  - 地址上下文搜索（用 address 字段中的城市/区信息辅助搜索）
  - 结果验证与重试（验证坐标是否在预期城市范围内）
  - 批量缓存

Usage:
    python scripts/geocode_places.py --input places.json --out geocoded.json --cache cache.json
"""

import argparse
import json
import sys
import os
import re
from typing import Dict, Optional

# 添加 src 到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from geocoding.nominatim import geocode_batch, geocode_single, generate_client_id
from geocoding.validator import (
    parse_address_levels, validate_geocode_result,
    haversine_distance, CITY_CENTERS,
)


# 主要城市 BBOX（lat_min, lat_max, lon_min, lon_max）用于快速判定
CITY_BBOX = {
    "上海": (30.6, 31.6, 120.8, 122.1),
    "北京": (39.7, 40.7, 115.9, 117.0),
    "广州": (22.8, 23.5, 113.0, 113.7),
    "深圳": (22.4, 22.8, 113.7, 114.4),
    "杭州": (29.9, 30.6, 119.8, 120.7),
    "南京": (31.7, 32.4, 118.4, 119.0),
    "苏州": (30.9, 31.6, 120.2, 121.1),
    "成都": (30.3, 30.9, 103.7, 104.3),
    "武汉": (30.3, 30.9, 114.0, 114.6),
    "重庆": (29.1, 29.9, 106.2, 107.0),
}


def extract_city_from_address(address: str) -> str:
    """从结构化地址中提取城市名"""
    parts = address.split("-")
    # address 格式: 中国-省-市-区-具体地点
    if len(parts) >= 3:
        return parts[2]
    return ""


def build_search_query(title: str, address: str) -> str:
    """构建更精确的搜索查询，附带城市上下文"""
    city = extract_city_from_address(address)
    district = ""
    parts = address.split("-")
    if len(parts) >= 4:
        district = parts[3]

    # 如果标题已包含城市名，直接用标题
    if city and city in title:
        return title

    # 否则附带城市上下文
    if city:
        return f"{title}, {city}"
    return title


def check_in_city_bbox(lat: float, lon: float, city: str) -> bool:
    """检查坐标是否在指定城市的 BBOX 内"""
    bbox = CITY_BBOX.get(city)
    if not bbox:
        return True  # 无 BBOX 数据，默认通过
    lat_min, lat_max, lon_min, lon_max = bbox
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def geocode_with_validation(
    title: str,
    address: str,
    cache: dict,
    sleep_sec: float = 1.0,
) -> Optional[Dict]:
    """对单个地点进行地理编码，带验证和重试"""

    # 构建搜索查询
    query = build_search_query(title, address)
    city = extract_city_from_address(address)
    parts = address.split("-")
    district = parts[3] if len(parts) >= 4 else ""

    # 检查缓存
    cache_key = f"{title}||{address}"
    if cache_key in cache:
        return cache[cache_key]

    # 第一次尝试
    result = geocode_single(query)

    if result:
        lat, lon = result["lat"], result["lon"]

        # 验证：如果期望在上海，检查是否在上海 BBOX 内
        if city and city in CITY_BBOX:
            if not check_in_city_bbox(lat, lon, city):
                print(f"  ⚠️  {title}: 结果({lat:.4f},{lon:.4f})不在{city}范围内，重试...")

                # 重试：用更具体的查询（标题 + 区 + 市）
                if district:
                    retry_query = f"{title}, {district}, {city}"
                else:
                    retry_query = f"{title}, {city}, 中国"

                import time
                time.sleep(sleep_sec)
                result = geocode_single(retry_query)

                if result and not check_in_city_bbox(result["lat"], result["lon"], city):
                    print(f"  ❌  {title}: 重试仍然不在{city}范围内，标记为失败")
                    result = None

        if result:
            geocode_result = {
                "lat": result["lat"],
                "lon": result["lon"],
                "display_name": result.get("display_name"),
                "locality": result.get("locality"),
                "countryCode": result.get("countryCode"),
                "osm_id": result.get("osm_id"),
                "osm_type": result.get("osm_type"),
            }
        else:
            geocode_result = None
    else:
        geocode_result = None

    cache[cache_key] = geocode_result
    return geocode_result


def main():
    parser = argparse.ArgumentParser(description="对地名进行地理编码（支持结构化输入）")
    parser.add_argument("--input", required=True, help="输入文件（JSON 数组或结构化 places JSON）")
    parser.add_argument("--out", required=True, help="输出文件")
    parser.add_argument("--cache", default="geocode_cache.json", help="缓存文件路径")
    parser.add_argument("--sleep", type=float, default=1.0, help="请求间隔秒数")
    parser.add_argument("--validate", action="store_true", help="启用结果验证")

    args = parser.parse_args()

    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 支持结构化输入（含 places 键）和扁平数组
        book_info = {}
        if isinstance(data, dict) and "places" in data:
            items = data["places"]
            book_info = data.get("book_info", {})
            print(f"📖 结构化输入: 《{book_info.get('title', '?')}》")
        elif isinstance(data, list):
            items = data
        else:
            print("❌ 输入格式错误: 需要 JSON 数组或含 places 键的对象")
            sys.exit(1)

        print(f"待编码地名: {len(items)} 个")

        # 加载缓存
        cache = {}
        if os.path.exists(args.cache):
            try:
                with open(args.cache, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
            except Exception:
                cache = {}

        # 逐个编码（带验证和重试）
        output = []
        success = 0
        failed = 0
        import time

        for i, item in enumerate(items):
            title = item.get("title", "")
            address = item.get("address", "")
            print(f"[{i+1}/{len(items)}] {title}...")

            geocode = geocode_with_validation(title, address, cache, args.sleep)

            output_item = {**item}

            if geocode:
                output_item["latitude"] = geocode["lat"]
                output_item["longitude"] = geocode["lon"]
                output_item["locality"] = geocode.get("locality")
                output_item["countryCode"] = geocode.get("countryCode")
                output_item["formattedAddress"] = geocode.get("display_name")
                output_item["clientId"] = generate_client_id(geocode, title)
                output_item["geocodeSuccess"] = True

                if args.validate and address:
                    levels = parse_address_levels(address)
                    validation = validate_geocode_result(levels, output_item)
                    output_item["validationPassed"] = validation["validation_passed"]

                success += 1
                print(f"  ✅ ({geocode['lat']:.4f}, {geocode['lon']:.4f})")
            else:
                output_item["geocodeSuccess"] = False
                failed += 1
                print(f"  ❌ 未找到")

            output.append(output_item)

            # 保存缓存
            if args.cache:
                os.makedirs(os.path.dirname(args.cache) or ".", exist_ok=True)
                with open(args.cache, 'w', encoding='utf-8') as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)

            time.sleep(args.sleep)

        # 写入输出
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 地理编码完成")
        print(f"   成功: {success}")
        print(f"   失败: {failed}")
        print(f"   输出文件: {args.out}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
