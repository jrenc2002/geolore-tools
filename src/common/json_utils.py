#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
故实巡礼 · 统一 JSON 解析工具

从 LLM 原始输出中提取 JSON，处理所有常见脏格式：
  - Markdown 代码块（包含嵌在文本中间的 ```json...``` 块）
  - google:search{...} 等工具调用前缀垃圾
  - BOM / 零宽字符
  - 尾随逗号
  - 控制字符
  - 括号未闭合（截断输出）
  - 混合文本 + JSON

用法:
    from src.common.json_utils import extract_json_from_text
    data = extract_json_from_text(llm_output)
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


def strip_code_fences(text: str) -> str:
    """移除 Markdown 代码块标记 (```json ... ```)，支持嵌在文本中间的情况"""
    text = text.strip()
    # 优先：找文本中任意位置的 ```json 或 ``` 代码块，提取最后一个代码块内容
    # 这能处理 "google:search{...}\n```json\n[...]\n```" 这类格式
    fenced = re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if fenced:
        # 返回最后一个（通常是真正的 JSON）
        return fenced[-1].strip()
    # 降级：文本以 ``` 开头
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _remove_bom(text: str) -> str:
    """移除 BOM / 零宽字符"""
    return text.lstrip("\ufeff\u200b\u200c\u200d")


def _fix_trailing_commas(text: str) -> str:
    """移除尾随逗号  ,] / ,}"""
    return re.sub(r",\s*([\]\}])", r"\1", text)


def _remove_control_chars(text: str) -> str:
    """移除控制字符（保留 \\n \\t）"""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+", " ", text)


def _strip_tool_call_prefix(text: str) -> str:
    """剥离 google:search{...} / tool_call{...} 等工具调用前缀，只保留其后的内容。

    模式：text 开头有若干 `identifier{...}` 或 `identifier{...}分隔符` 这样的块，
    真正的 JSON 数组/对象在这些块之后。
    策略：找到最后一个 `}` 后第一个 `[` 或 `{` 的位置作为 JSON 起点。
    """
    # 找所有 ```json 或 ``` 内容（已在 strip_code_fences 处理，这里是 fallback）
    # 直接寻找独立顶层 [ ... ] 或 { ... }，跳过嵌在 word{} 内的括号
    # 方法：扫描文本，遇到不在任何单词标识符后的 [ 或 { 才视为 JSON 起点
    # 简化：找所有顶层 [ 的候选位置，排除 `word[` 形式（工具调用内的数组）
    # 具体：找 "非字母数字字符 + [" 或 行首/空白后的 [ 作为 JSON 数组起点
    candidates = []
    for m in re.finditer(r'(?<![A-Za-z0-9_:{,])\[', text):
        candidates.append(m.start())
    for start in candidates:
        # 尝试从这个 [ 开始做括号匹配找完整数组
        segment = _extract_balanced(text, start, "[", "]")
        if segment:
            result = _try_parse(segment)
            if result is not _SENTINEL and isinstance(result, list):
                return segment
    return text


def _extract_balanced(text: str, start: int, opener: str, closer: str) -> Optional[str]:
    """从 start 位置开始，用括号深度匹配提取完整的 opener...closer 片段。"""
    if start >= len(text) or text[start] != opener:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start: i + 1]
    return None


def _try_parse(text: str) -> Any:
    """安静地尝试解析，失败返回 _SENTINEL"""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return _SENTINEL


_SENTINEL = object()


def extract_json_from_text(text: str) -> Any:
    """从 LLM 输出中尽最大努力提取 JSON。

    尝试策略（按优先级）：
      1. 提取 ```json...``` 代码块（支持嵌在文本中间）
      2. 直接解析（去 BOM 后）
      3. 剥离工具调用前缀，用括号深度匹配定位顶层 JSON 数组
      4. 定位最外层 [ ... ] 或 { ... }（rfind 方式）
      5. 修复常见语法错误后再尝试
      6. 逐步截断 + 自动闭合括号

    Returns:
        解析后的 Python 对象（dict / list / str / ...），
        完全无法解析时返回 None。
    """
    if not text or not text.strip():
        return None

    # ── 第一步：优先提取 ```json...``` 代码块 ──
    # 支持代码块嵌在文本任意位置（处理 google:search 前缀 + ```json 块）
    fenced_blocks = re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    for block in reversed(fenced_blocks):  # 优先最后一个代码块
        block = _remove_bom(block.strip())
        block_fixed = _fix_trailing_commas(_remove_control_chars(block))
        result = _try_parse(block_fixed)
        if result is not _SENTINEL:
            return result
        result = _try_parse(block)
        if result is not _SENTINEL:
            return result

    # ── 第二步：基本清理后直接解析 ──
    cleaned = strip_code_fences(text)
    cleaned = _remove_bom(cleaned)

    result = _try_parse(cleaned)
    if result is not _SENTINEL:
        return result

    # ── 第三步：括号深度匹配（跳过工具调用前缀） ──
    # 找所有"不紧跟在标识符之后"的 [ 作为 JSON 数组候选起点
    stripped = _strip_tool_call_prefix(cleaned)
    if stripped != cleaned:
        result = _try_parse(stripped)
        if result is not _SENTINEL:
            return result
        fixed = _fix_trailing_commas(_remove_control_chars(stripped))
        result = _try_parse(fixed)
        if result is not _SENTINEL:
            return result

    # ── 第四步：rfind 定位最外层 [ ... ] 或 { ... } ──
    for opener, closer in [("[", "]"), ("{", "}")]:
        start = cleaned.find(opener)
        end = cleaned.rfind(closer)
        if start != -1 and end > start:
            result = _try_parse(cleaned[start: end + 1])
            if result is not _SENTINEL:
                return result

    # ── 第五步：修复常见语法错误 ──
    fixed = _fix_trailing_commas(_remove_control_chars(cleaned))
    for opener, closer in [("[", "]"), ("{", "}")]:
        s = fixed.find(opener)
        e = fixed.rfind(closer)
        if s != -1 and e > s:
            result = _try_parse(fixed[s: e + 1])
            if result is not _SENTINEL:
                return result

    # ── 第六步：截断 + 自动闭合（处理截断输出） ──
    # 使用括号深度匹配找最靠后的顶层 [ 起点
    arr_start = -1
    for m in re.finditer(r'(?<![A-Za-z0-9_:{,])\[', cleaned):
        arr_start = m.start()  # 取最后一个候选
    if arr_start == -1:
        arr_start = cleaned.find("[")  # 降级 fallback
    if arr_start != -1:
        fragment = cleaned[arr_start:]
        for trim_back in range(0, min(500, len(fragment)), 10):
            candidate = fragment[: len(fragment) - trim_back].rstrip().rstrip(",")
            open_braces = candidate.count("{") - candidate.count("}")
            open_brackets = candidate.count("[") - candidate.count("]")
            candidate += "}" * max(0, open_braces) + "]" * max(0, open_brackets)
            result = _try_parse(candidate)
            if result is not _SENTINEL:
                return result

    print(f"  ⚠️  JSON 解析彻底失败: {text[:120]}...")
    return None


def extract_json_array(text: str) -> Optional[str]:
    """从文本中提取 JSON 数组子串（原始字符串）。

    与 extract_json_from_text 不同，此函数返回的是字符串而非解析后的对象，
    保留供 cleaner 的逐字符匹配逻辑使用。
    """
    text = strip_code_fences(text)
    first = text.find("[")
    last = text.rfind("]")

    if first == -1 or last == -1 or last <= first:
        return None

    candidate = text[first : last + 1]
    result = _try_parse(candidate)
    if result is not _SENTINEL:
        return candidate

    # 逐字符匹配最外层 [ ... ]
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "[":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0 and start != -1:
                segment = text[start : i + 1]
                r = _try_parse(segment)
                if r is not _SENTINEL:
                    return segment
    return None
