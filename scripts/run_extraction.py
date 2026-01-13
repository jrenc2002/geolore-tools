#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM 抽取执行命令行工具

Usage:
    python scripts/run_extraction.py --prompts prompts.jsonl --out extracted/ --api-key $API_KEY
"""

import argparse
import sys
import os

# 添加 src 到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from extraction.llm_runner import run_extraction, LLMConfig


def main():
    parser = argparse.ArgumentParser(
        description="调用 LLM API 执行文本信息抽取"
    )
    parser.add_argument(
        "--prompts", 
        required=True,
        help="JSONL 格式的提示词文件"
    )
    parser.add_argument(
        "--out", 
        required=True,
        help="输出目录"
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("OPENAI_API_KEY"),
        help="LLM API Key（默认从 OPENAI_API_KEY 环境变量读取）"
    )
    parser.add_argument(
        "--base-url",
        default="https://api.openai.com/v1/chat/completions",
        help="API Base URL"
    )
    parser.add_argument(
        "--model",
        default="gpt-4",
        help="模型名称（默认: gpt-4）"
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=1.0,
        help="请求间隔秒数（默认: 1.0）"
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="不跳过已存在的输出文件"
    )
    
    args = parser.parse_args()
    
    if not args.api_key:
        print("❌ 错误: 请提供 API Key（--api-key 或设置 OPENAI_API_KEY 环境变量）")
        sys.exit(1)
    
    config = LLMConfig(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model
    )
    
    try:
        result = run_extraction(
            args.prompts, 
            args.out, 
            config,
            rate_limit_delay=args.rate_limit,
            skip_existing=not args.no_skip
        )
        print(f"\n✅ 抽取完成")
        print(f"   总任务数: {result['total']}")
        print(f"   成功: {result['success']}")
        print(f"   跳过: {result['skipped']}")
        print(f"   失败: {result['failed']}")
        print(f"   输出目录: {result['output_dir']}")
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
