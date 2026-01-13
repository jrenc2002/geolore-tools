#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM 抽取执行器 - 调用 LLM API 执行文本信息抽取

功能：
 - 支持多种 LLM API（OpenAI 兼容、Claude 等）
 - 自动重试和错误处理
 - 支持断点续传
 - 结果缓存

注意：API Key 应通过环境变量或配置文件提供，不要硬编码
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """LLM 配置"""
    api_key: str
    base_url: str = "https://api.openai.com/v1/chat/completions"
    model: str = "gpt-4"
    temperature: float = 0.1
    timeout: int = 60
    retry_count: int = 3
    retry_delay: float = 2.0


def clean_json_response(content: str) -> str:
    """清理 LLM 返回的 JSON 内容（移除 markdown 代码块标记）"""
    content = content.strip()
    
    # 移除开头的 markdown 代码块标记
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    
    # 移除结尾的 markdown 代码块标记
    if content.endswith("```"):
        content = content[:-3]
    
    return content.strip()


def call_llm(
    text: str, 
    instructions: str, 
    schema: dict,
    config: LLMConfig
) -> Optional[Dict]:
    """
    调用 LLM API
    
    Args:
        text: 输入文本
        instructions: 抽取指令
        schema: 输出 schema
        config: LLM 配置
    
    Returns:
        解析后的 JSON 结果，失败返回 None
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.api_key}"
    }
    
    # 构建系统提示词
    system_prompt = (
        f"{instructions}\n\n"
        "IMPORTANT: You must output ONLY valid JSON. No markdown code blocks, no explanations.\n"
        f"Strictly follow this schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}"
    )
    
    data = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "temperature": config.temperature
    }
    
    for attempt in range(config.retry_count):
        try:
            req = urllib.request.Request(
                config.base_url, 
                data=json.dumps(data).encode('utf-8'), 
                headers=headers
            )
            
            with urllib.request.urlopen(req, timeout=config.timeout) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result['choices'][0]['message']['content']
                content = clean_json_response(content)
                return json.loads(content)
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f"HTTP Error {e.code} (attempt {attempt + 1}): {error_body}")
            
            # 429 或 5xx 错误时重试
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(config.retry_delay * (attempt + 1))
                continue
            return None
            
        except json.JSONDecodeError as e:
            print(f"JSON decode error (attempt {attempt + 1}): {e}")
            if attempt < config.retry_count - 1:
                time.sleep(config.retry_delay)
                continue
            return None
            
        except Exception as e:
            print(f"Error calling API (attempt {attempt + 1}): {e}")
            if attempt < config.retry_count - 1:
                time.sleep(config.retry_delay)
                continue
            return None
    
    return None


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
