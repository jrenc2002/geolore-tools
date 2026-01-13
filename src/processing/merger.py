#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
合并提取结果 - 将散落在不同章节的同一地点合并

输入: JSONL 格式，每行包含一个章节的提取结果
  {"chunkFile": "chunk_001.txt", "output": [{"title": "...", "address": "...", "story": "..."}]}

输出: JSON 数组
  [{"title": "...", "address": "...", "story": ["...", "..."]}]

规则:
- 按 title (去除空白后) 精确匹配分组
- address 采用多数投票法 (出现次数最多的)，平票时用第一个出现的
- story 保留为数组，去重但保持首次出现顺序

使用示例:
  python merger.py --input extracted.jsonl --output merged.json
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, OrderedDict
from typing import Any, Dict, List


def read_lines(path: str):
    """逐行读取文件"""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield line


def parse_jsonl(path: str):
    """解析 JSONL 文件"""
    for line in read_lines(path):
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def merge_by_title(jsonl_path: str) -> List[Dict[str, Any]]:
    """
    按 title 合并提取结果
    
    Args:
        jsonl_path: 输入 JSONL 文件路径
        
    Returns:
        合并后的地点列表
    """
    groups: Dict[str, Dict[str, Any]] = {}

    for obj in parse_jsonl(jsonl_path):
        outputs = obj.get("output")
        if not isinstance(outputs, list):
            continue
            
        for item in outputs:
            if not isinstance(item, dict):
                continue
                
            title = item.get("title")
            address = item.get("address")
            story = item.get("story")
            
            # 验证字段类型
            if not isinstance(title, str) or not isinstance(address, str) or not isinstance(story, str):
                continue
                
            title_key = title.strip()
            address_val = address.strip()
            story_val = story.strip()
            
            if not title_key:
                continue

            # 获取或创建分组
            g = groups.get(title_key)
            if g is None:
                g = {
                    "title": title_key,
                    "address_counter": Counter(),
                    "address_first": None,
                    "stories_seen": OrderedDict(),  # 保持插入顺序的去重集合
                }
                groups[title_key] = g

            # 统计 address
            if address_val:
                g["address_counter"][address_val] += 1
                if g["address_first"] is None:
                    g["address_first"] = address_val
                    
            # 去重添加 story
            if story_val and story_val not in g["stories_seen"]:
                g["stories_seen"][story_val] = True

    # 构建结果数组
    result: List[Dict[str, Any]] = []
    
    for title_key, g in groups.items():
        # 选择最佳 address (多数投票)
        address = ""
        if g["address_counter"]:
            most_common = g["address_counter"].most_common()
            max_count = most_common[0][1]
            candidates = [addr for addr, cnt in most_common if cnt == max_count]
            
            if len(candidates) == 1:
                address = candidates[0]
            else:
                # 平票时使用首次出现的
                first = g["address_first"]
                address = first if first in candidates else candidates[0]

        stories = list(g["stories_seen"].keys())
        
        result.append({
            "title": title_key,
            "address": address,
            "story": stories,
        })

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="合并提取结果 - 按 title 分组，story 合并为数组"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="输入 JSONL 文件路径 (如 extracted.jsonl)"
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="输出 JSON 文件路径 (如 merged.json)"
    )
    args = parser.parse_args()

    merged = merge_by_title(args.input)
    
    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
    
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
        
    print(f"✓ 合并完成: {args.output} ({len(merged)} 个唯一地点)")


if __name__ == "__main__":
    main()
