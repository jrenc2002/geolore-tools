#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM 提示词生成器 - 为文本分片生成结构化的 LLM 提示词

功能：
 - 为每个文本分片生成 JSONL 格式的提示词
 - 支持自定义抽取指令和 schema
 - 支持多种抽取场景（小说地点、人物生平等）

输出 JSONL 格式：
{
  "chunkFile": "...",
  "input": {
    "instructions": "...",
    "schema": { ... },
    "text": "<chunk content>"
  }
}
"""

from __future__ import annotations

import json
import os
import glob
from typing import Dict, List, Optional, Callable


def default_place_extraction_instructions() -> str:
    """默认的地点抽取指令"""
    return (
        "你是信息抽取助手。阅读给定文本分片，抽取以下要素：\n"
        "1) 地点（places）：尽量给出最具体的地名，保留同义/别名。\n"
        "2) 节日（festivals）：含地域性节日/庙会/××节等，如能从文本判断时间（公历/农历/大致月份）也一并给出。\n"
        "3) 组织（organizations）：如'长春会'等非地点名词。\n"
        "4) 关联（links）：将节日与地点关联、组织与地点关联，附带证据片段（quote）与在分片中的字符偏移（offsetStart/offsetEnd）。\n"
        "要求：\n"
        "- 尽量结构化输出；字段不存在时置 null；不要添加未定义字段。\n"
        "- quote 控制在 120 字以内；\n"
        "- 如果无法确定准确地点，也可关联到上级行政区并标注 granularity=admin。\n"
    )


def default_place_extraction_schema() -> dict:
    """默认的地点抽取 schema"""
    return {
        "places": [
            {
                "name": "string",
                "alias": ["string"],
                "granularity": "poi|street|district|city|province|country|null",
                "evidence": {
                    "offsetStart": 0,
                    "offsetEnd": 0,
                    "quote": "string"
                }
            }
        ],
        "festivals": [
            {
                "name": "string",
                "date": "YYYY-MM-DD|null",
                "timeOfYear": "如 每年正月/春节前后|null",
                "evidence": {"offsetStart": 0, "offsetEnd": 0, "quote": "string"}
            }
        ],
        "organizations": [
            {
                "name": "string",
                "type": "guild|society|secret|other|null",
                "evidence": {"offsetStart": 0, "offsetEnd": 0, "quote": "string"}
            }
        ],
        "links": [
            {
                "type": "festival_at_place|organization_at_place|mention",
                "source": "string",
                "targetPlace": "string|null",
                "confidence": 0.0,
                "evidence": {"offsetStart": 0, "offsetEnd": 0, "quote": "string"}
            }
        ]
    }


def timeline_extraction_instructions() -> str:
    """人物生平/时间线抽取指令"""
    return (
        "你是信息抽取助手。阅读给定文本，按时间顺序抽取人物行踪和重要事件。\n"
        "对于每个事件，提取：\n"
        "1) 时间（年份或日期）\n"
        "2) 地点名称（尽量具体，如古今对应地名都给出）\n"
        "3) 事件摘要（100字以内）\n"
        "4) 原文引用（证据片段）\n"
        "要求：\n"
        "- 严格按照给定 schema 输出 JSON；\n"
        "- 时间格式：年份用 YYYY，日期用 YYYY-MM-DD，不确定的留 null；\n"
        "- 地点要尽量准确，保留古地名和现代对应；\n"
    )


def timeline_extraction_schema() -> dict:
    """人物生平/时间线抽取 schema"""
    return {
        "events": [
            {
                "dateStart": "YYYY|YYYY-MM|YYYY-MM-DD|null",
                "dateEnd": "YYYY|YYYY-MM|YYYY-MM-DD|null",
                "location": {
                    "ancientName": "string|null",
                    "modernName": "string|null",
                    "province": "string|null",
                    "city": "string|null"
                },
                "synopsis": "string",
                "quote": "string",
                "orderIndex": 0
            }
        ]
    }


# 预设模板
PRESET_TEMPLATES = {
    "place": {
        "instructions": default_place_extraction_instructions,
        "schema": default_place_extraction_schema
    },
    "timeline": {
        "instructions": timeline_extraction_instructions,
        "schema": timeline_extraction_schema
    }
}


def generate_prompts(
    chunks_dir: str,
    output_jsonl: str,
    instructions: Optional[str] = None,
    schema: Optional[dict] = None,
    template: str = "place"
) -> Dict:
    """
    为文本分片生成 LLM 提示词
    
    Args:
        chunks_dir: 分片目录
        output_jsonl: 输出 JSONL 文件路径
        instructions: 自定义指令（如为 None 则使用模板）
        schema: 自定义 schema（如为 None 则使用模板）
        template: 预设模板名称（place/timeline）
    
    Returns:
        处理结果统计
    """
    # 获取指令和 schema
    if template in PRESET_TEMPLATES:
        tmpl = PRESET_TEMPLATES[template]
        if instructions is None:
            instructions = tmpl["instructions"]()
        if schema is None:
            schema = tmpl["schema"]()
    else:
        if instructions is None:
            instructions = default_place_extraction_instructions()
        if schema is None:
            schema = default_place_extraction_schema()
    
    # 查找分片文件
    files = sorted(glob.glob(os.path.join(chunks_dir, "chunk_*.txt")))
    
    # 生成提示词
    os.makedirs(os.path.dirname(output_jsonl) or ".", exist_ok=True)
    
    with open(output_jsonl, "w", encoding="utf-8") as out:
        for fn in files:
            with open(fn, "r", encoding="utf-8") as f:
                text = f.read()
            
            obj = {
                "chunkFile": fn,
                "input": {
                    "instructions": instructions,
                    "schema": schema,
                    "text": text,
                },
            }
            out.write(json.dumps(obj, ensure_ascii=False) + "\n")
    
    return {
        "chunks_dir": chunks_dir,
        "output_file": output_jsonl,
        "total_prompts": len(files),
        "template": template
    }


def load_prompts(jsonl_path: str) -> List[Dict]:
    """
    加载 JSONL 格式的提示词
    
    Args:
        jsonl_path: JSONL 文件路径
    
    Returns:
        提示词列表
    """
    prompts = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                prompts.append(json.loads(line))
    return prompts
