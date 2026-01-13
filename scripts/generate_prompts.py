#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM 提示词生成命令行工具

Usage:
    python scripts/generate_prompts.py --chunks chunks/ --out prompts.jsonl --template place
"""

import argparse
import sys
import os

# 添加 src 到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from extraction.prompt_generator import generate_prompts, PRESET_TEMPLATES


def main():
    parser = argparse.ArgumentParser(
        description="为文本分片生成 LLM 提示词"
    )
    parser.add_argument(
        "--chunks", 
        required=True,
        help="分片目录"
    )
    parser.add_argument(
        "--out", 
        required=True,
        help="输出 JSONL 文件路径"
    )
    parser.add_argument(
        "--template", 
        default="place",
        choices=list(PRESET_TEMPLATES.keys()),
        help="预设模板（默认: place）"
    )
    
    args = parser.parse_args()
    
    try:
        result = generate_prompts(args.chunks, args.out, template=args.template)
        print(f"✅ 提示词生成完成")
        print(f"   分片目录: {result['chunks_dir']}")
        print(f"   输出文件: {result['output_file']}")
        print(f"   提示词数: {result['total_prompts']}")
        print(f"   使用模板: {result['template']}")
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
