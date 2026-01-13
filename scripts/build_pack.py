#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
内容包构建命令行工具

Usage:
    python scripts/build_pack.py --input geocoded.json --out pack.json --pack-id my-pack --title "我的地图"
"""

import argparse
import json
import sys
import os

# 添加 src 到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from packing.pack_builder import (
    PackConfig, 
    build_place, 
    build_map_place,
    build_content_pack, 
    write_content_pack,
    merge_places
)


def main():
    parser = argparse.ArgumentParser(
        description="将地理编码结果打包为 Geolore 内容包"
    )
    parser.add_argument(
        "--input", 
        required=True,
        help="输入文件（地理编码后的 JSON）"
    )
    parser.add_argument(
        "--out", 
        required=True,
        help="输出文件"
    )
    parser.add_argument(
        "--pack-id",
        required=True,
        help="内容包 ID"
    )
    parser.add_argument(
        "--title",
        help="内容包标题"
    )
    parser.add_argument(
        "--version",
        type=int,
        default=1,
        help="内容包版本（默认: 1）"
    )
    parser.add_argument(
        "--map-title",
        help="地图标题（默认使用内容包标题）"
    )
    parser.add_argument(
        "--tags",
        nargs="*",
        help="标签列表"
    )
    parser.add_argument(
        "--schema-version",
        type=int,
        default=1,
        choices=[1, 2],
        help="协议版本（1 或 2，默认: 1）"
    )
    
    args = parser.parse_args()
    
    try:
        # 读取输入
        with open(args.input, 'r', encoding='utf-8') as f:
            items = json.load(f)
        
        # 构建 places
        places = []
        map_places = []
        order = 1
        
        for item in items:
            # 跳过编码失败的
            if not item.get("geocodeSuccess") and not (item.get("latitude") and item.get("longitude")):
                continue
            
            # 构建 place
            name = item.get("title") or item.get("name")
            geocode = {
                "lat": item.get("latitude"),
                "lon": item.get("longitude"),
                "locality": item.get("locality"),
                "countryCode": item.get("countryCode"),
                "display_name": item.get("formattedAddress"),
                "osm_type": item.get("osm_type"),
                "osm_id": item.get("osm_id"),
            }
            
            place = build_place(
                name=name,
                geocode_result=geocode,
                client_id=item.get("clientId"),
                synopsis=item.get("synopsis"),
                timeline=item.get("timeline")
            )
            
            if place:
                places.append(place)
                
                # 构建 mapPlace
                map_place = build_map_place(
                    place_client_id=place["clientId"],
                    order_index=order,
                    note=item.get("synopsis") or item.get("note")
                )
                map_places.append(map_place)
                order += 1
        
        # 去重
        places = merge_places(places)
        
        # 构建配置
        config = PackConfig(
            pack_id=args.pack_id,
            version=args.version,
            title=args.title,
            map_title=args.map_title or args.title or "地图",
            tags=args.tags
        )
        
        # 构建内容包
        content_pack = build_content_pack(
            config=config,
            places=places,
            map_places=map_places,
            schema_version=args.schema_version
        )
        
        # 写入文件
        write_content_pack(content_pack, args.out)
        
        print(f"\n✅ 内容包构建完成")
        print(f"   Pack ID: {args.pack_id}")
        print(f"   版本: {args.version}")
        print(f"   地点数: {len(places)}")
        print(f"   输出文件: {args.out}")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
