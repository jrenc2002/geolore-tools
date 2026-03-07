#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
故实巡礼 · 书籍注册表（记忆系统）

管理已处理/已推荐的书籍列表，防止重复推荐。
支持增量追加、标签统计、覆盖分析等。

文件格式：registry.json
{
  "schema_version": 1,
  "books": [...],
  "stats": {...}
}
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set


DEFAULT_REGISTRY_PATH = "output/registry.json"


def _empty_registry() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "books": [],
        "stats": {
            "total_books": 0,
            "by_language": {},
            "by_type": {},
            "by_region": {},
            "by_grade": {},
        },
    }


def load_registry(path: str = DEFAULT_REGISTRY_PATH) -> Dict[str, Any]:
    """加载书籍注册表，不存在则返回空注册表"""
    if not os.path.exists(path):
        return _empty_registry()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_registry(registry: Dict[str, Any], path: str = DEFAULT_REGISTRY_PATH) -> None:
    """保存书籍注册表"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    _recompute_stats(registry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def _recompute_stats(registry: Dict[str, Any]) -> None:
    """重新计算统计信息"""
    books = registry.get("books", [])
    stats = {
        "total_books": len(books),
        "by_language": {},
        "by_type": {},
        "by_region": {},
        "by_grade": {},
    }
    for b in books:
        lang = b.get("language", "unknown")
        stats["by_language"][lang] = stats["by_language"].get(lang, 0) + 1

        btype = b.get("type", "unknown")
        stats["by_type"][btype] = stats["by_type"].get(btype, 0) + 1

        region = b.get("geo_region", "unknown")
        stats["by_region"][region] = stats["by_region"].get(region, 0) + 1

        grade = b.get("grade", "?")
        stats["by_grade"][grade] = stats["by_grade"].get(grade, 0) + 1

    registry["stats"] = stats


def get_existing_titles(registry: Dict[str, Any]) -> Set[str]:
    """获取已有书名集合（中文+英文+别名全部收集）"""
    titles = set()
    for b in registry.get("books", []):
        if b.get("title"):
            titles.add(b["title"])
        if b.get("title_en"):
            titles.add(b["title_en"])
        for alias in b.get("aliases", []):
            titles.add(alias)
    return titles


def add_book(
    registry: Dict[str, Any],
    title: str,
    author: str,
    language: str = "zh",
    book_type: str = "novel",
    grade: str = "S",
    geo_region: str = "",
    geo_scope: str = "",
    era_setting: str = "",
    place_count_estimate: int = 0,
    density_index: float = 0.0,
    reachability_pct: int = 0,
    route_shape: str = "network",
    reason: str = "",
    title_en: str = "",
    aliases: Optional[List[str]] = None,
    status: str = "recommended",  # recommended | processing | completed | skipped
    extra: Optional[Dict] = None,
) -> Dict[str, Any]:
    """添加一本书到注册表，返回新增的书籍记录"""
    book = {
        "title": title,
        "title_en": title_en,
        "aliases": aliases or [],
        "author": author,
        "language": language,
        "type": book_type,
        "grade": grade,
        "geo_region": geo_region,
        "geo_scope": geo_scope,
        "era_setting": era_setting,
        "place_count_estimate": place_count_estimate,
        "density_index": density_index,
        "reachability_pct": reachability_pct,
        "route_shape": route_shape,
        "reason": reason,
        "status": status,
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        book.update(extra)

    registry.setdefault("books", []).append(book)
    return book


def build_memory_block(registry: Dict[str, Any]) -> str:
    """
    构建一段文本「记忆块」，用于注入到 LLM prompt 中。
    包括：已生成书目列表、覆盖统计、空白区域提示。
    """
    books = registry.get("books", [])
    stats = registry.get("stats", {})

    if not books:
        return "（暂无已处理书籍，这是第一次选题。）"

    lines = []
    lines.append(f"═══ 已处理/已推荐书籍清单（共 {len(books)} 部）═══")
    lines.append("")

    # 按语言分组展示
    zh_books = [b for b in books if b.get("language", "zh") == "zh"]
    en_books = [b for b in books if b.get("language", "zh") == "en"]
    other_books = [b for b in books if b.get("language", "zh") not in ("zh", "en")]

    def _format_book_list(book_list: List[Dict], label: str) -> None:
        if not book_list:
            return
        lines.append(f"── {label} ({len(book_list)} 部) ──")
        for b in book_list:
            grade = b.get("grade", "?")
            title = b.get("title", "?")
            author = b.get("author", "?")
            btype = b.get("type", "?")
            region = b.get("geo_region", "?")
            status = b.get("status", "?")
            status_icon = {"recommended": "📋", "processing": "⏳", "completed": "✅", "skipped": "⏭️"}.get(status, "?")
            lines.append(f"  {status_icon} [{grade}] 《{title}》{author} | {btype} | {region}")
        lines.append("")

    _format_book_list(zh_books, "中文作品")
    _format_book_list(en_books, "英文作品")
    _format_book_list(other_books, "其他语言")

    # 覆盖统计
    lines.append("── 覆盖统计 ──")
    by_type = stats.get("by_type", {})
    if by_type:
        lines.append(f"  类型分布: {', '.join(f'{k}={v}' for k, v in sorted(by_type.items()))}")
    by_region = stats.get("by_region", {})
    if by_region:
        lines.append(f"  地区分布: {', '.join(f'{k}={v}' for k, v in sorted(by_region.items()))}")
    by_lang = stats.get("by_language", {})
    if by_lang:
        lines.append(f"  语言分布: {', '.join(f'{k}={v}' for k, v in sorted(by_lang.items()))}")
    lines.append("")

    # 空白区提示
    all_regions = {b.get("geo_region", "") for b in books}
    all_types = {b.get("type", "") for b in books}

    suggested_regions = {"华东", "华南", "华北", "西南", "西北", "东北", "华中",
                         "港澳台", "东南亚", "日本", "欧洲", "北美", "南美",
                         "中东", "非洲", "大洋洲", "中亚", "南亚", "英国", "法国"}
    missing_regions = suggested_regions - all_regions

    suggested_types = {"novel", "travelogue", "biography", "poetry", "history", "folklore", "essay"}
    missing_types = suggested_types - all_types

    if missing_regions or missing_types:
        lines.append("── 空白区域（优先填充）──")
        if missing_regions:
            lines.append(f"  未覆盖地区: {', '.join(sorted(missing_regions))}")
        if missing_types:
            lines.append(f"  未覆盖类型: {', '.join(sorted(missing_types))}")

    return "\n".join(lines)


def build_exclusion_list(registry: Dict[str, Any]) -> str:
    """构建排除列表（纯书名列表），用于短提示注入"""
    titles = get_existing_titles(registry)
    if not titles:
        return ""
    return "、".join(f"《{t}》" for t in sorted(titles))
