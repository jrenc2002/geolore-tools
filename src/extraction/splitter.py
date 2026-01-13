#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
文本分片器 - 将长篇文本按章节分割为便于 LLM 处理的小片段

功能：
 - 支持中文章节标题识别（第X章、第X回等）
 - 可配置每个分片包含的章节数
 - 自动生成索引文件

输出：
 - <out_dir>/chunk_XXX.txt: 每个分片的文本文件
 - <out_dir>/index.json: 章节元数据（偏移量、范围）
"""

from __future__ import annotations

import json
import os
import re
from typing import List, Tuple, Dict


# 章节标题正则表达式
CHAPTER_PATTERNS = [
    re.compile(r"第[一二三四五六七八九十〇零百千0-9]+章[ \t\u3000]*[\S ]*"),  # 第X章
    re.compile(r"第[一二三四五六七八九十〇零百千0-9]+回[ \t\u3000]*[\S ]*"),  # 第X回
    re.compile(r"第[一二三四五六七八九十〇零百千0-9]+节[ \t\u3000]*[\S ]*"),  # 第X节
    re.compile(r"第[一二三四五六七八九十〇零百千0-9]+卷[ \t\u3000]*[\S ]*"),  # 第X卷
]


def read_text(path: str) -> str:
    """读取文本文件"""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def normalize(text: str) -> str:
    """
    文本规范化处理
    - 移除中文字符间的垂直线（如 北|京）
    - 压缩连续换行符
    """
    # 移除中文字符间的垂直线
    text = re.sub(r"(?<=[\u4e00-\u9fff])\|(?=[\u4e00-\u9fff])", "", text)
    # 压缩 3+ 换行符为 2 个
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def find_chapters(text: str, patterns: List[re.Pattern] = None) -> List[Tuple[int, str]]:
    """
    查找所有章节标题
    
    Args:
        text: 输入文本
        patterns: 章节标题正则列表，默认使用 CHAPTER_PATTERNS
    
    Returns:
        [(position, title), ...] 章节位置和标题列表
    """
    if patterns is None:
        patterns = CHAPTER_PATTERNS
    
    chapters: List[Tuple[int, str]] = []
    for pattern in patterns:
        for m in pattern.finditer(text):
            chapters.append((m.start(), m.group().strip()))
    
    # 按位置排序并去重
    chapters = sorted(set(chapters), key=lambda x: x[0])
    return chapters


def slice_chunks(text: str, chapters: List[Tuple[int, str]], per_chunk: int = 2) -> List[Dict]:
    """
    将文本按章节分割为块
    
    Args:
        text: 输入文本
        chapters: 章节列表 [(position, title), ...]
        per_chunk: 每个分片包含的章节数
    
    Returns:
        分片列表，每个元素包含 start, end, chapters, text
    """
    if not chapters:
        # 无章节时将整个文本作为一个块
        return [{"start": 0, "end": len(text), "chapters": ["全文"], "text": text}]

    # 构建章节范围
    ranges: List[Dict] = []
    for idx, (start, name) in enumerate(chapters):
        end = chapters[idx + 1][0] if idx + 1 < len(chapters) else len(text)
        ranges.append({"name": name, "start": start, "end": end})

    # 按 per_chunk 分组
    chunks: List[Dict] = []
    for i in range(0, len(ranges), per_chunk):
        group = ranges[i : i + per_chunk]
        start = group[0]["start"]
        end = group[-1]["end"]
        chunk_text = text[start:end]
        chunk_meta = {
            "start": start, 
            "end": end, 
            "chapters": [r["name"] for r in group], 
            "text": chunk_text
        }
        chunks.append(chunk_meta)
    
    return chunks


def write_chunks(out_dir: str, chunks: List[Dict]) -> Dict:
    """
    将分片写入文件
    
    Args:
        out_dir: 输出目录
        chunks: 分片列表
    
    Returns:
        索引信息
    """
    os.makedirs(out_dir, exist_ok=True)
    index = []
    
    for i, ch in enumerate(chunks, start=1):
        fn = os.path.join(out_dir, f"chunk_{i:03d}.txt")
        with open(fn, "w", encoding="utf-8") as f:
            f.write(ch["text"])
        index.append({
            "file": fn, 
            "chapters": ch["chapters"], 
            "start": ch["start"], 
            "end": ch["end"], 
            "length": len(ch["text"])
        })
    
    index_path = os.path.join(out_dir, "index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    
    return {"total_chunks": len(chunks), "index_path": index_path}


def split_text(text_path: str, out_dir: str, per_chunk: int = 2, 
               custom_patterns: List[re.Pattern] = None) -> Dict:
    """
    主函数：分割文本文件
    
    Args:
        text_path: 输入文本路径
        out_dir: 输出目录
        per_chunk: 每个分片包含的章节数
        custom_patterns: 自定义章节正则表达式列表
    
    Returns:
        处理结果统计
    """
    text = read_text(text_path)
    text = normalize(text)
    chapters = find_chapters(text, custom_patterns)
    chunks = slice_chunks(text, chapters, per_chunk)
    result = write_chunks(out_dir, chunks)
    
    return {
        "input_file": text_path,
        "output_dir": out_dir,
        "total_chars": len(text),
        "total_chapters": len(chapters),
        **result
    }
