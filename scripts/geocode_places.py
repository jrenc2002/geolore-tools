#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
地理编码命令行工具

Usage:
    python scripts/geocode_places.py --input places.json --out geocoded.json --cache cache.json
"""

import argparse
import json
import sys
import os

# 添加 src 到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from geocoding.nominatim import geocode_batch, generate_client_id
from geocoding.validator import parse_address_levels, validate_geocode_result


def main():
    parser = argparse.ArgumentParser(
        description="对地名进行地理编码"
    )
    parser.add_argument(
        "--input", 
        required=True,
        help="输入文件（JSON 数组，每项需有 title 或 name 字段）"
    )
    parser.add_argument(
        "--out", 
        required=True,
        help="输出文件"
    )
    parser.add_argument(
        "--cache",
        default="geocode_cache.json",
        help="缓存文件路径"
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="请求间隔秒数（默认: 1.0）"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="启用结果验证"
    )
    
    args = parser.parse_args()
    
    try:
        # 读取输入
        with open(args.input, 'r', encoding='utf-8') as f:
            items = json.load(f)
        
        # 提取地名
        names = []
        for item in items:
            name = item.get("title") or item.get("name") or item.get("address")
            if name:
                names.append(name)
        
        names = list(set(names))  # 去重
        print(f"待编码地名: {len(names)} 个")
        
        # 批量编码
        results = geocode_batch(names, args.cache, args.sleep)
        
        # 构建输出
        output = []
        success = 0
        failed = 0
        
        for item in items:
            name = item.get("title") or item.get("name") or item.get("address")
            geocode = results.get(name)
            
            output_item = {**item}
            
            if geocode:
                output_item["latitude"] = geocode["lat"]
                output_item["longitude"] = geocode["lon"]
                output_item["locality"] = geocode.get("locality")
                output_item["countryCode"] = geocode.get("countryCode")
                output_item["formattedAddress"] = geocode.get("display_name")
                output_item["clientId"] = generate_client_id(geocode, name)
                output_item["geocodeSuccess"] = True
                
                # 验证
                if args.validate and item.get("address"):
                    levels = parse_address_levels(item["address"])
                    validation = validate_geocode_result(levels, output_item)
                    output_item["validationPassed"] = validation["validation_passed"]
                
                success += 1
            else:
                output_item["geocodeSuccess"] = False
                failed += 1
            
            output.append(output_item)
        
        # 写入输出
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 地理编码完成")
        print(f"   成功: {success}")
        print(f"   失败: {failed}")
        print(f"   输出文件: {args.out}")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
