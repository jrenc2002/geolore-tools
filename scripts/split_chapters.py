#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
文本分片命令行工具

Usage:
    python scripts/split_chapters.py --text input.txt --out-dir chunks/ --per-chunk 2
"""

import argparse
import sys
import os

# 添加 src 到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from extraction.splitter import split_text


def main():
    parser = argparse.ArgumentParser(
        description="将长篇文本按章节分割为便于 LLM 处理的小片段"
    )
    parser.add_argument(
        "--text", 
        required=True,
        help="输入文本文件路径"
    )
    parser.add_argument(
        "--out-dir", 
        required=True,
        help="输出目录"
    )
    parser.add_argument(
        "--per-chunk", 
        type=int, 
        default=2,
        help="每个分片包含的章节数（默认: 2）"
    )
    
    args = parser.parse_args()
    
    try:
        result = split_text(args.text, args.out_dir, args.per_chunk)
        print(f"✅ 分片完成")
        print(f"   输入文件: {result['input_file']}")
        print(f"   总字符数: {result['total_chars']}")
        print(f"   总章节数: {result['total_chapters']}")
        print(f"   输出分片: {result['total_chunks']} 个")
        print(f"   输出目录: {result['output_dir']}")
        print(f"   索引文件: {result['index_path']}")
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
