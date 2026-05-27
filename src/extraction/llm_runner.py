#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM 抽取执行器 - 调用 LLM API 执行文本信息抽取

功能：
 - 支持多种 LLM API（OpenAI 兼容）
 - 自动重试和错误处理
 - 支持断点续传
 - 结果缓存

底层调用已统一到 src.common.llm_client，此模块仅保留面向
"JSONL 批量抽取" 的上层逻辑。

注意：API Key 应通过环境变量或配置文件提供，不要硬编码
"""

from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional, Any

# ── 统一导入 ──
try:
    from src.common.config import LLMConfig
    from src.common.llm_client import call_llm_for_extraction
    from src.common.json_utils import strip_code_fences
except ImportError:
    from common.config import LLMConfig
    from common.llm_client import call_llm_for_extraction
    from common.json_utils import strip_code_fences  # 向后兼容别名


# ── 向后兼容：保留 clean_json_response 作为别名 ──
clean_json_response = strip_code_fences


def call_llm(
    text: str,
    instructions: str,
    schema: dict,
    config: LLMConfig,
) -> Optional[Dict]:
    """向后兼容的 call_llm 包装器，内部委托给统一实现。"""
    return call_llm_for_extraction(text, instructions, schema, config)


def run_extraction(
    prompts_file: str,
    output_dir: str,
    config: LLMConfig,
    rate_limit_delay: float = 1.0,
    skip_existing: bool = True
) -> Dict:
    """
    批量执行 LLM 抽取
    
    Args:
        prompts_file: JSONL 格式的提示词文件
        output_dir: 输出目录
        config: LLM 配置
        rate_limit_delay: 请求间隔（秒）
        skip_existing: 是否跳过已存在的输出
    
    Returns:
        处理结果统计
    """
    if not os.path.exists(prompts_file):
        raise FileNotFoundError(f"Prompts file not found: {prompts_file}")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 读取提示词
    with open(prompts_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    total = len(lines)
    success = 0
    skipped = 0
    failed = 0
    
    print(f"Found {total} chunks to process.")
    
    for i, line in enumerate(lines):
        try:
            item = json.loads(line)
            chunk_file = item['chunkFile']
            input_data = item['input']
            
            # 构建输出文件名
            basename = os.path.basename(chunk_file)
            output_filename = f"output_{basename.replace('.txt', '.json')}"
            output_path = os.path.join(output_dir, output_filename)
            
            # 跳过已存在的文件
            if skip_existing and os.path.exists(output_path):
                print(f"[{i+1}/{total}] Skipping {basename}, already exists.")
                skipped += 1
                continue
            
            print(f"[{i+1}/{total}] Processing {basename}...")
            
            # 调用 LLM
            result = call_llm(
                input_data['text'], 
                input_data['instructions'], 
                input_data['schema'],
                config
            )
            
            if result:
                final_output = {
                    "chunkFile": basename,
                    "output": result
                }
                
                with open(output_path, 'w', encoding='utf-8') as out:
                    json.dump(final_output, out, ensure_ascii=False, indent=2)
                print(f"  -> Saved to {output_filename}")
                success += 1
            else:
                print("  -> Failed to get valid result")
                failed += 1
            
            # 速率限制
            time.sleep(rate_limit_delay)
            
        except json.JSONDecodeError:
            print(f"Skipping line {i+1}: Invalid JSON in prompts file")
            failed += 1
        except Exception as e:
            print(f"Error processing line {i+1}: {e}")
            failed += 1
    
    return {
        "total": total,
        "success": success,
        "skipped": skipped,
        "failed": failed,
        "output_dir": output_dir
    }


def load_extraction_results(output_dir: str) -> List[Dict]:
    """
    加载抽取结果
    
    Args:
        output_dir: 输出目录
    
    Returns:
        结果列表
    """
    results = []
    
    for filename in sorted(os.listdir(output_dir)):
        if filename.startswith("output_") and filename.endswith(".json"):
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                results.append(json.load(f))
    
    return results
