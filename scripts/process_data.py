#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据处理流水线 - 串联合并、清洗和过滤步骤

功能：
 1. 合并同名地点 (Merger)
 2. LLM 批量清洗 (Cleaner)
 3. 过滤无效数据 (Filter)

Usage:
    python scripts/process_data.py --input extracted.jsonl --output ready_to_geocode.jsonl --api-key sk-...
"""

import argparse
import asyncio
import json
import os
import sys
from typing import List, Dict, Any

# 添加 src 到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from processing.merger import merge_by_title
from processing.cleaner import run_batches, APIConfig
from processing.filter import filter_items


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    return items


def save_jsonl(path: str, items: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


async def async_main(args):
    # 1. Merger
    print(f"=== Stage 1: Merging duplicate places from {args.input} ===")
    # merge_by_title 接受 JSONL 文件路径
    merged_items = merge_by_title(args.input)
    print(f"Merged into {len(merged_items)} unique places.")
    
    # 可选：保存合并后的中间结果
    if args.save_intermediate:
        mid_path = args.output + ".merged.json"
        with open(mid_path, "w", encoding="utf-8") as f:
            json.dump(merged_items, f, indent=2, ensure_ascii=False)
        print(f"saved intermediate merged data to {mid_path}")

    # 2. Cleaner
    print("=== Stage 2: Cleaning synopsis with LLM ===")
    if not args.prompt_file:
        # 默认找 prompts/cleaning.md
        default_prompt = os.path.join(os.path.dirname(__file__), "..", "prompts", "cleaning.md")
        if os.path.exists(default_prompt):
            args.prompt_file = default_prompt
        else:
            print("Error: --prompt-file not specified and default prompts/cleaning.md not found.")
            sys.exit(1)
            
    print(f"Using prompt file: {args.prompt_file}")
    with open(args.prompt_file, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    config = APIConfig(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        temperature=0.1,
        timeout=60
    )
    
    # Cleaner 会生成临时文件 batch_results.jsonl 和 cleaned_output.json
    temp_batch = args.output + ".batch.jsonl"
    temp_cleaned = args.output + ".cleaned.json"
    
    # 如果已经有 cleaned file 且开启了 resume，可能不需要全部重跑，但这里简单起见，调用 run_batches
    await run_batches(
        config=config,
        system_prompt=system_prompt,
        items=merged_items,
        batch_size=args.batch_size,
        batch_jsonl=temp_batch,
        output_json=temp_cleaned,
        max_concurrency=args.concurrency,
        retries=3,
        rate_limit=10.0, # 默认 10 RPS
        resume=True,
        quiet=False
    )
    
    # Load cleaned items
    if os.path.exists(temp_cleaned):
        with open(temp_cleaned, "r", encoding="utf-8") as f:
            cleaned_items = json.load(f)
        print(f"Cleaned {len(cleaned_items)} places.")
    else:
        print("Error: Cleaning failed, output file not found.")
        sys.exit(1)

    # 3. Filter
    print("=== Stage 3: Filtering invalid places ===")
    final_items = filter_items(cleaned_items)
    print(f"Filtered down to {len(final_items)} valid places.")
    
    # Save final output
    save_jsonl(args.output, final_items)
    print(f"=== Done! Saved result to {args.output} ===")


def main():
    parser = argparse.ArgumentParser(description="运行 geolore 数据处理流水线 (Merge -> Clean -> Filter)")
    
    parser.add_argument("--input", required=True, help="输入文件 (LLM 提取后的 JSONL)")
    parser.add_argument("--output", required=True, help="输出文件 (准备进行 geocoding 的 JSONL)")
    
    # LLM config
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY"), help="API Key")
    parser.add_argument("--base-url", default="https://api.openai.com/v1/chat/completions", help="API Base URL")
    parser.add_argument("--model", default="gpt-4o", help="Model name")
    parser.add_argument("--prompt-file", help="Prompt file path (default: prompts/cleaning.md)")
    
    # Runtime config
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for checking")
    parser.add_argument("--concurrency", type=int, default=5, help="Async concurrency")
    parser.add_argument("--save-intermediate", action="store_true", help="Save intermediate merged files")
    
    args = parser.parse_args()
    
    if not args.api_key:
        print("Error: --api-key is required (or set OPENAI_API_KEY env var)")
        sys.exit(1)
        
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
