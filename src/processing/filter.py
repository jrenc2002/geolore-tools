#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据过滤器 - 移除无效或过于宽泛的地址

规则:
- 删除地址仅为省级行政区名称的记录 (如 "河北省")
- 删除标题或地址包含"未知"、"未找到"等标记的记录

输入: JSON 数组 [{title, address, synopsis}]
输出: 过滤后的 JSON 数组

使用示例:
  python filter.py --input cleaned.json --output filtered.json
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Set


# 省级行政区名称集合
PROVINCE_LEVEL_ONLY: Set[str] = {
    # 省
    "河北省", "山西省", "辽宁省", "吉林省", "黑龙江省",
    "江苏省", "浙江省", "安徽省", "福建省", "江西省",
    "山东省", "河南省", "湖北省", "湖南省", "广东省",
    "海南省", "四川省", "贵州省", "云南省", "陕西省",
    "甘肃省", "青海省", "台湾省",
    # 自治区
    "内蒙古自治区", "广西壮族自治区", "西藏自治区", 
    "宁夏回族自治区", "新疆维吾尔自治区",
    # 直辖市（作为省级）
    "北京市", "天津市", "上海市", "重庆市",
    # 特别行政区
    "香港特别行政区", "澳门特别行政区",
}

# 无效标记
UNKNOWN_MARKERS: Set[str] = {
    "未找到", "未知", "未知地点", "名称未知", 
    "地点未知", "未知地址", "未知名称",
}


def contains_unknown(text: str) -> bool:
    """检查文本是否包含无效标记"""
    return any(marker in text for marker in UNKNOWN_MARKERS)


def is_province_only(address: str) -> bool:
    """检查地址是否仅为省级名称"""
    return address in PROVINCE_LEVEL_ONLY


def should_drop(item: Dict[str, Any]) -> bool:
    """判断记录是否应被丢弃"""
    title = str(item.get("title", "")).strip()
    address = str(item.get("address", "")).strip()
    
    if not title or not address:
        return True
        
    # 标题或地址包含未知标记
    if contains_unknown(title) or contains_unknown(address):
        return True
        
    # 地址仅为省级名称
    if is_province_only(address):
        return True
        
    return False


def filter_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """过滤地点列表"""
    filtered: List[Dict[str, Any]] = []
    
    for item in items:
        if not isinstance(item, dict):
            continue
            
        # 规范化字段
        title = str(item.get("title", "")).strip()
        address = str(item.get("address", "")).strip()
        synopsis = str(item.get("synopsis", "")).strip()
        
        normalized = {
            "title": title, 
            "address": address, 
            "synopsis": synopsis
        }
        
        if not should_drop(normalized):
            filtered.append(normalized)
            
    return filtered


def main() -> None:
    parser = argparse.ArgumentParser(
        description="过滤无效/宽泛地址"
    )
    parser.add_argument(
        "--input", "-i",
        default="cleaned.json",
        help="输入 JSON 文件路径"
    )
    parser.add_argument(
        "--output", "-o",
        default="filtered.json",
        help="输出 JSON 文件路径"
    )
    args = parser.parse_args()

    # 读取输入
    with open(args.input, "r", encoding="utf-8") as f:
        items = json.load(f)
        
    if not isinstance(items, list):
        raise ValueError("输入 JSON 必须是数组")

    before = len(items)
    filtered = filter_items(items)
    after = len(filtered)

    # 写入输出
    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
    
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(filtered, f, ensure_ascii=False, indent=2)

    print(f"✓ 过滤完成: 保留 {after}/{before} (移除 {before - after}) → {args.output}")


if __name__ == "__main__":
    main()
