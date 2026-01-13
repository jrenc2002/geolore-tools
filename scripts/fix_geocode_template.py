#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
地理编码修复脚本模板

当自动地理编码返回错误结果时，使用此脚本进行手动修复。
复制此文件到项目目录，根据实际情况修改 FIX_RULES。

使用方法:
    python fix_geocode.py --input geocoded.json --output fixed.json

示例 (繁花项目 - 上海地点):
    - 目标区域: 上海市
    - 坐标范围: 纬度 30-32°N, 经度 120-122°E
"""

import json
import time
import urllib.parse
import urllib.request
import argparse
from typing import Dict, Any, Optional

# ============================================================
# 配置区域 - 根据项目修改
# ============================================================

# 高德 API Key (从环境变量获取更安全)
import os
AMAP_KEY = os.environ.get("AMAP_KEY", "your_amap_key_here")

# 目标区域的坐标范围
VALID_LAT_RANGE = (30, 32)   # 纬度范围
VALID_LON_RANGE = (120, 122)  # 经度范围

# 默认搜索城市
DEFAULT_CITY = "上海"

# 手动修正规则: 地点名称 -> 更精确的查询词
# 当某个地点无法自动正确解析时，添加规则
FIX_RULES = {
    # 示例规则 (来自繁花项目)
    "复兴公园": "复兴公园 复兴中路 黄浦",
    "三官堂桥造纸厂": "三官堂桥 普陀",
    "两万户": "两万户 曹杨新村",
    "人民广场派出所": "人民广场 派出所",
    "光复西路苏州河": "光复西路 苏州河 普陀",
    "公交医院": "公交医院 上海",
    "南昌公寓": "南昌公寓 南昌路 黄浦",
    "叶家宅小菜场": "叶家宅路 普陀 菜场",
    "向明中学": "向明中学 上海",
    "唐韵": "唐韵 南京东路",
    "夜东京": "夜东京 进贤路",
    "大光明电影院": "大光明电影院 南京西路",
    "大都会舞厅": "大都会 南京西路 舞厅",
    "太平洋": "太平洋百货 南京东路",
    "平安电影院": "平安电影院 南京西路",
    "沪西饭店": "沪西饭店 曹家渡",
    "波特曼": "波特曼丽思卡尔顿 南京西路",
    "淮海路国营旧货店": "淮海路 旧货店",
    "皋兰路尼古拉斯东正教堂": "皋兰路 东正教堂 黄浦",
    "花园饭店": "花园饭店 上海",
    "贵都": "贵都大酒店 华山路",
    "金门饭店": "金门大酒店 南京东路",
    "铜仁路上海咖啡馆": "铜仁路 咖啡馆",
    "长乐中学": "长乐中学 瑞金路",
    "长宁电影院": "长宁电影院 愚园路",
}

# 手动指定坐标 (当 API 完全无法找到时)
MANUAL_COORDS = {
    # "地点名称": (纬度, 经度, "区域名称"),
    # 示例:
    # "大都会舞厅": (31.229, 121.451, "静安区"),
}

# ============================================================
# 核心函数
# ============================================================

def amap_search(query: str, city: str = DEFAULT_CITY) -> Optional[Dict]:
    """使用高德 API 搜索地点"""
    base = "https://restapi.amap.com/v3/place/text"
    params = {
        "key": AMAP_KEY,
        "keywords": query,
        "city": city,
        "citylimit": "true",  # 关键: 限制搜索范围
        "output": "JSON"
    }
    url = f"{base}?{urllib.parse.urlencode(params)}"
    
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())
            if data.get("status") == "1" and data.get("pois"):
                poi = data["pois"][0]
                loc = poi.get("location", "")
                if "," in loc:
                    lon, lat = map(float, loc.split(","))
                    return {
                        "latitude": lat,
                        "longitude": lon,
                        "name": poi.get("name"),
                        "address": poi.get("address"),
                        "locality": poi.get("adname")
                    }
    except Exception as e:
        print(f"  ERROR: {e}")
    
    time.sleep(0.5)  # API 限流
    return None


def is_in_valid_region(lat: float, lon: float) -> bool:
    """检查坐标是否在有效区域内"""
    return (VALID_LAT_RANGE[0] <= lat <= VALID_LAT_RANGE[1] and
            VALID_LON_RANGE[0] <= lon <= VALID_LON_RANGE[1])


def fix_place(item: Dict) -> Dict:
    """修复单个地点的坐标"""
    title = item.get("title", "")
    lat = item.get("latitude")
    lon = item.get("longitude")
    
    # 检查是否需要修复
    if lat and lon and is_in_valid_region(lat, lon):
        return item  # 坐标正确，无需修复
    
    print(f"\n修复: {title}")
    print(f"  原坐标: ({lat}, {lon})")
    
    # 方法1: 检查手动坐标表
    if title in MANUAL_COORDS:
        manual = MANUAL_COORDS[title]
        item["latitude"] = manual[0]
        item["longitude"] = manual[1]
        item["locality"] = manual[2]
        item["fixMethod"] = "manual"
        print(f"  ✓ 手动修复: ({manual[0]}, {manual[1]})")
        return item
    
    # 方法2: 使用修正规则重新查询
    if title in FIX_RULES:
        query = FIX_RULES[title]
        print(f"  查询: {query}")
        result = amap_search(query)
        
        if result and is_in_valid_region(result["latitude"], result["longitude"]):
            item["latitude"] = result["latitude"]
            item["longitude"] = result["longitude"]
            item["locality"] = result.get("locality", "")
            item["fixMethod"] = "rule_based"
            print(f"  ✓ 规则修复: ({result['latitude']}, {result['longitude']})")
            return item
    
    # 方法3: 尝试 title + 城市名
    query = f"{title} {DEFAULT_CITY}"
    print(f"  尝试: {query}")
    result = amap_search(query)
    
    if result and is_in_valid_region(result["latitude"], result["longitude"]):
        item["latitude"] = result["latitude"]
        item["longitude"] = result["longitude"]
        item["locality"] = result.get("locality", "")
        item["fixMethod"] = "city_suffix"
        print(f"  ✓ 城市后缀修复: ({result['latitude']}, {result['longitude']})")
        return item
    
    # 修复失败
    print(f"  ✗ 修复失败，需要手动处理")
    item["fixMethod"] = "failed"
    return item


def main():
    parser = argparse.ArgumentParser(description="修复地理编码错误")
    parser.add_argument("--input", "-i", required=True, help="输入 JSON 文件")
    parser.add_argument("--output", "-o", required=True, help="输出 JSON 文件")
    parser.add_argument("--dry-run", action="store_true", help="只检查，不修复")
    args = parser.parse_args()
    
    # 读取数据
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # 统计
    total = len(data)
    need_fix = 0
    fixed = 0
    failed = 0
    
    # 处理每个地点
    for item in data:
        lat = item.get("latitude")
        lon = item.get("longitude")
        
        if not (lat and lon and is_in_valid_region(lat, lon)):
            need_fix += 1
            
            if not args.dry_run:
                fix_place(item)
                if item.get("fixMethod") != "failed":
                    fixed += 1
                else:
                    failed += 1
    
    # 输出结果
    print(f"\n{'='*50}")
    print(f"总计: {total} 个地点")
    print(f"需要修复: {need_fix} 个")
    
    if not args.dry_run:
        print(f"成功修复: {fixed} 个")
        print(f"修复失败: {failed} 个")
        
        # 保存结果
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到: {args.output}")
    
    # 列出失败的地点
    if failed > 0:
        print(f"\n需要手动处理的地点:")
        for item in data:
            if item.get("fixMethod") == "failed":
                print(f"  - {item['title']}")


if __name__ == "__main__":
    main()
