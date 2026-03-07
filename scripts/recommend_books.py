#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
故实巡礼 · AI 选书推荐（带记忆系统）

每次运行：
  1. 加载 registry.json（已选书目）
  2. 构建记忆块注入到 prompt
  3. 调用 LLM 推荐新书
  4. 将推荐结果追加到 registry.json

用法：
  # 推荐 5 本新书（单次模式）
  python scripts/recommend_books.py --count 5

  # 选书侦察模式：推荐 20 本，每轮 5 本，共 4 轮 API 调用，附排名
  python scripts/recommend_books.py --mode scout --count 20

  # 选书侦察 + 自定义每轮数量
  python scripts/recommend_books.py --mode scout --count 30 --batch-size 5

  # 指定偏好地区和类型
  python scripts/recommend_books.py --count 10 --prefer-region "日本,欧洲" --prefer-type "travelogue,biography"

  # 只打印 prompt，不调用 API（手动使用）
  python scripts/recommend_books.py --dump-prompt --count 5

  # 导入外部 JSON 推荐结果
  python scripts/recommend_books.py --import-file recommendations.json

  # 查看当前注册表状态
  python scripts/recommend_books.py --status

  # 推荐完成后直接进入 pipeline 处理
  python scripts/recommend_books.py --count 5 --auto-pipeline

环境变量：
  GEOLORE_API_KEY: API 密钥
  GEOLORE_BASE_URL: API 基础 URL
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import math
from typing import Any, Dict, List, Optional

# 添加项目根目录到 path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.common.config import (
    LLMConfig,
    MODEL_CLAUDE,
    MODEL_PRO,
    PROVIDER_CLAUDE,
    PROVIDER_GEMINI,
    load_llm_config,
)
from src.common.llm_client import call_llm
from src.common.json_utils import extract_json_from_text

from src.memory.book_registry import (
    load_registry,
    save_registry,
    add_book,
    build_memory_block,
    build_exclusion_list,
    get_existing_titles,
)

# ─────────────────────────── Config ───────────────────────────

DEFAULT_REGISTRY = "output/data/registry.json"

# ─────────────────────────── Prompt Builder ───────────────────

SYSTEM_PROMPT = """你是「故实巡礼」(Geolore) 的选题编辑 AI。

故实巡礼是一款将文学作品中的地点提取为地理坐标、让用户在现实世界中"巡礼"的应用。
你的任务是推荐最适合被"地理化"的书籍——那些天然带有空间坐标基因、
且能通过地理位置产生阅读增量价值的内容。

核心原则：
1. 绝不推荐记忆清单中已有的书籍
2. 主动填充覆盖空白（未覆盖的地区和类型优先）
3. 中英文作品兼收，优先选择受众广泛的
4. 每部作品必须通过选题价值边界评估
5. 优先推荐在该语言/地区的读者群体中具有较高知名度的作品"""


def build_user_prompt(
    count: int,
    memory_block: str,
    exclusion_list: str,
    prefer_region: str = "",
    prefer_type: str = "",
    prefer_language: str = "",
    extra_instructions: str = "",
) -> str:
    """构建用户 prompt"""

    preference_section = ""
    if prefer_region or prefer_type or prefer_language:
        pref_lines = ["六、本次偏好（优先但不强制）"]
        pref_lines.append("═══════════════════════════════════════════════════════════")
        if prefer_region:
            pref_lines.append(f"  偏好地区: {prefer_region}")
        if prefer_type:
            pref_lines.append(f"  偏好类型: {prefer_type}")
        if prefer_language:
            pref_lines.append(f"  偏好语言: {prefer_language}")
        pref_lines.append("")
        preference_section = "\n".join(pref_lines)

    extra_section = ""
    if extra_instructions:
        extra_section = f"\n七、额外指令\n═══════════════════════════════════════════════════════════\n{extra_instructions}\n"

    prompt = f"""═══════════════════════════════════════════════════════════
故实巡礼 · 选书推荐引擎 (Book Recommendation Engine)
═══════════════════════════════════════════════════════════

一、选题价值边界（必须满足才推荐）
═══════════════════════════════════════════════════════════

一部书值得被"地理化"，当且仅当它满足以下条件之一：

┌──────────────────┬──────────────────────────────────────────────┐
│ 空间叙事型        │ 核心叙事围绕真实地理空间展开                    │
│ 文化地标型        │ 将特定地点升华为文化符号                        │
│ 行程轨迹型        │ 存在可复现的真实行程线路                        │
└──────────────────┴──────────────────────────────────────────────┘

不推荐：纯虚构世界观、地点模糊化处理、已被过度地图化的经典、地点密度<1。

二、记忆系统（严禁推荐以下书目）
═══════════════════════════════════════════════════════════

{memory_block}

严禁推荐的书目列表：{exclusion_list}

三、量化评估体系
═══════════════════════════════════════════════════════════

对每本推荐书目必须计算：
  - 地点密度指数 = 预估可提取真实地点数 ÷ 总万字数。≥5优秀/3-5良好/<1不推荐
  - 现实可达率 = 今日可到达的地点占比。≥80%优秀
  - 路线形态：线状(游记) > 网状(城市) > 点状(诗集)
  - 巡礼吸引力：1-10，读者会因此书想去打卡吗？
  - 受众规模：massive/large/medium/niche

四、输出要求
═══════════════════════════════════════════════════════════

推荐 {count} 部书籍。中英文比例大约 6:4，优先选择受众多的。

输出纯 JSON 数组，每个元素：
{{{{
  "rank": 排名,
  "title": "书名（原文）",
  "title_en": "英文名/英文原名（中文书给英文译名，英文书给原名）",
  "author": "作者",
  "language": "zh|en|ja|fr|...",
  "type": "novel|travelogue|biography|poetry|history|folklore|essay",
  "era_setting": "故事发生的时代背景",
  "geo_region": "主要地理区域标签",
  "geo_scope": "具体地理范围描述",
  "word_count_estimate": 估算万字数,
  "place_count_estimate": 预估可提取地点数,
  "density_index": 地点密度指数,
  "reachability_pct": 现实可达率(0-100),
  "route_shape": "linear|network|scattered",
  "pilgrimage_appeal": 巡礼吸引力(1-10),
  "audience_size": "massive|large|medium|niche",
  "geo_added_value": "high|medium|low",
  "timeline_needed": true/false,
  "grade": "S|A|B",
  "reason": "80字以内的推荐理由",
  "value_boundary": "spatial_narrative|cultural_landmark|route_trace"
}}}}

五、多样性要求
═══════════════════════════════════════════════════════════

基于记忆中的覆盖统计，优先推荐未覆盖地区/类型/语言的作品。
确保推荐不同城市/地区/类型的作品，避免扎堆。

{preference_section}{extra_section}只输出 JSON 数组，不要任何其他内容。"""

    return prompt


# ─────────────────────────── Commands ─────────────────────────


def cmd_status(registry_path: str) -> None:
    """显示注册表状态"""
    registry = load_registry(registry_path)
    books = registry.get("books", [])
    stats = registry.get("stats", {})

    print(f"\n{'='*50}")
    print(f"📊 故实巡礼 · 书籍注册表状态")
    print(f"{'='*50}")
    print(f"总书目: {len(books)}")

    if not books:
        print("（空注册表，尚未推荐任何书籍）")
        return

    # 按状态统计
    statuses = {}
    for b in books:
        s = b.get("status", "unknown")
        statuses[s] = statuses.get(s, 0) + 1
    print(f"\n状态分布:")
    for s, c in sorted(statuses.items()):
        icon = {"recommended": "📋", "processing": "⏳", "completed": "✅", "skipped": "⏭️"}.get(s, "?")
        print(f"  {icon} {s}: {c}")

    by_lang = stats.get("by_language", {})
    if by_lang:
        print(f"\n语言分布: {', '.join(f'{k}={v}' for k, v in sorted(by_lang.items()))}")

    by_type = stats.get("by_type", {})
    if by_type:
        print(f"类型分布: {', '.join(f'{k}={v}' for k, v in sorted(by_type.items()))}")

    by_region = stats.get("by_region", {})
    if by_region:
        print(f"地区分布: {', '.join(f'{k}={v}' for k, v in sorted(by_region.items()))}")

    print(f"\n── 书目列表 ──")
    for i, b in enumerate(books, 1):
        grade = b.get("grade", "?")
        title = b.get("title", "?")
        author = b.get("author", "?")
        lang = b.get("language", "?")
        region = b.get("geo_region", "?")
        status = b.get("status", "?")
        icon = {"recommended": "📋", "processing": "⏳", "completed": "✅", "skipped": "⏭️"}.get(status, "?")
        print(f"  {i:2d}. {icon} [{grade}] 《{title}》{author} | {lang} | {region}")


def cmd_recommend(
    count: int,
    config: LLMConfig,
    registry_path: str,
    prefer_region: str = "",
    prefer_type: str = "",
    prefer_language: str = "",
    extra_instructions: str = "",
    dump_prompt: bool = False,
    auto_pipeline: bool = False,
) -> List[Dict]:
    """执行推荐"""
    registry = load_registry(registry_path)
    memory_block = build_memory_block(registry)
    exclusion_list = build_exclusion_list(registry)

    user_prompt = build_user_prompt(
        count=count,
        memory_block=memory_block,
        exclusion_list=exclusion_list,
        prefer_region=prefer_region,
        prefer_type=prefer_type,
        prefer_language=prefer_language,
        extra_instructions=extra_instructions,
    )

    if dump_prompt:
        print("═══ SYSTEM PROMPT ═══")
        print(SYSTEM_PROMPT)
        print("\n═══ USER PROMPT ═══")
        print(user_prompt)
        return []

    print(f"\n{'='*50}")
    print(f"📚 故实巡礼 · AI 选书推荐")
    print(f"{'='*50}")
    print(f"  已有书目: {len(registry.get('books', []))}")
    print(f"  请求推荐: {count} 部")
    print(f"  模型: {config.model}")
    if prefer_region:
        print(f"  偏好地区: {prefer_region}")
    if prefer_type:
        print(f"  偏好类型: {prefer_type}")
    print()

    # 调用 LLM
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    print("  🤖 正在请求 AI 推荐...")
    content = call_llm(
        messages=messages,
        config=config,
        temperature=0.7,
    )

    recommendations = extract_json_from_text(content)
    if not isinstance(recommendations, list):
        print(f"  ❌ 解析失败，原始输出:\n{content[:500]}")
        # 保存原始输出以便调试
        raw_file = os.path.join(os.path.dirname(registry_path), "last_recommendation_raw.txt")
        os.makedirs(os.path.dirname(raw_file) or ".", exist_ok=True)
        with open(raw_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  💾 原始输出已保存到: {raw_file}")
        return []

    # 去重：检查是否有已存在的书被推荐（AI 偶尔出错）
    existing = get_existing_titles(registry)
    new_recs = []
    for rec in recommendations:
        title = rec.get("title", "")
        if title in existing:
            print(f"  ⚠️  跳过已有书目: 《{title}》")
            continue
        new_recs.append(rec)

    print(f"\n  ✅ 获得 {len(new_recs)} 部新推荐：\n")
    for rec in new_recs:
        grade = rec.get("grade", "?")
        title = rec.get("title", "?")
        author = rec.get("author", "?")
        lang = rec.get("language", "?")
        region = rec.get("geo_region", "?")
        density = rec.get("density_index", "?")
        reach = rec.get("reachability_pct", "?")
        appeal = rec.get("pilgrimage_appeal", "?")
        reason = rec.get("reason", "")
        print(f"  [{grade}] 《{title}》{author}")
        print(f"      语言:{lang} | 地区:{region} | 密度:{density} | 可达:{reach}% | 吸引力:{appeal}")
        print(f"      理由: {reason}")
        print()

    # 追加到注册表
    for rec in new_recs:
        add_book(
            registry,
            title=rec.get("title", ""),
            author=rec.get("author", ""),
            language=rec.get("language", "zh"),
            book_type=rec.get("type", "novel"),
            grade=rec.get("grade", "B"),
            geo_region=rec.get("geo_region", ""),
            geo_scope=rec.get("geo_scope", ""),
            era_setting=rec.get("era_setting", ""),
            place_count_estimate=rec.get("place_count_estimate", 0),
            density_index=rec.get("density_index", 0.0),
            reachability_pct=rec.get("reachability_pct", 0),
            route_shape=rec.get("route_shape", "network"),
            reason=rec.get("reason", ""),
            title_en=rec.get("title_en", ""),
            status="recommended",
            extra={
                "pilgrimage_appeal": rec.get("pilgrimage_appeal", 0),
                "audience_size": rec.get("audience_size", ""),
                "geo_added_value": rec.get("geo_added_value", ""),
                "value_boundary": rec.get("value_boundary", ""),
                "timeline_needed": rec.get("timeline_needed", False),
            },
        )

    save_registry(registry, registry_path)
    print(f"  💾 注册表已更新: {registry_path} (总计 {len(registry['books'])} 部)")

    # 保存本次推荐的原始数据
    rec_file = os.path.join(
        os.path.dirname(registry_path),
        f"recommendation_{int(time.time())}.json",
    )
    with open(rec_file, "w", encoding="utf-8") as f:
        json.dump(new_recs, f, ensure_ascii=False, indent=2)
    print(f"  💾 本次推荐详情: {rec_file}")

    # 自动进入 pipeline
    if auto_pipeline and new_recs:
        s_books = [r for r in new_recs if r.get("grade") == "S"]
        if s_books:
            print(f"\n  🚀 自动进入 pipeline 处理 {len(s_books)} 部 S 级作品...")
            for sb in s_books:
                cmd = (
                    f"python scripts/auto_pipeline.py --mode specify "
                    f"--work \"{sb['title']}\" "
                    f"--author \"{sb.get('author', '未知')}\" "
                    f"--work-type \"{sb.get('type', 'novel')}\" "
                    f"--era \"{sb.get('era_setting', '')}\" "
                    f"--geo-scope \"{sb.get('geo_scope', '')}\""
                )
                print(f"     → {cmd}")

    return new_recs


# ─────────────── 地图价值评分 ─────────────────────────


def compute_geo_score(book: Dict) -> float:
    """计算单本书的地图价值综合评分 (0-100)

    权重分配：
      地点密度指数  25%  (归一化到 0-10 → 0-25)
      现实可达率    20%  (0-100 → 0-20)
      巡礼吸引力    20%  (1-10  → 0-20)
      路线形态      10%  (linear=10, network=7, scattered=4)
      受众规模      10%  (massive=10, large=8, medium=5, niche=3)
      地理化增量价值 15%  (high=15, medium=10, low=5)
    """
    density = min(book.get("density_index", 0), 10) / 10 * 25
    reach = book.get("reachability_pct", 0) / 100 * 20
    appeal = min(book.get("pilgrimage_appeal", 0), 10) / 10 * 20

    shape_map = {"linear": 10, "network": 7, "scattered": 4}
    shape = shape_map.get(book.get("route_shape", ""), 4) / 10 * 10

    audience_map = {"massive": 10, "large": 8, "medium": 5, "niche": 3}
    audience = audience_map.get(book.get("audience_size", ""), 3) / 10 * 10

    value_map = {"high": 15, "medium": 10, "low": 5}
    added_value = value_map.get(book.get("geo_added_value", ""), 5)

    return round(density + reach + appeal + shape + audience + added_value, 1)


def grade_from_score(score: float) -> str:
    """根据综合分自动判定等级"""
    if score >= 75:
        return "S"
    elif score >= 55:
        return "A"
    else:
        return "B"


# ─────────────── 选书侦察模式 (Scout Mode) ─────────────


def cmd_scout(
    total: int,
    config: LLMConfig,
    registry_path: str,
    prefer_region: str = "",
    prefer_type: str = "",
    prefer_language: str = "",
    extra_instructions: str = "",
    batch_size: int = 5,
    dry_run: bool = False,
    replay_raw_dir: str = "",
) -> List[Dict]:
    """选书侦察模式

    专注于选书，多轮调用 API，每轮 batch_size 本。
    每轮结果立即写入注册表，下一轮可看到更新后的记忆。
    全部完成后按地图价值综合评分排名输出。

    Args:
        total:        目标总推荐数量
        config:       LLM 配置
        registry_path: 注册表路径
        prefer_region: 偏好地区
        prefer_type:   偏好类型
        prefer_language: 偏好语言
        extra_instructions: 额外指令
        batch_size:   每轮推荐数量 (默认 5)
        dry_run:      仅打印 prompt 不调用
    """
    rounds = math.ceil(total / batch_size)
    all_new_books: List[Dict] = []

    print(f"\n{'═'*60}")
    print(f"📚 故实巡礼 · 选书侦察模式 (Scout Mode)")
    print(f"{'═'*60}")
    print(f"  目标数量: {total} 部")
    print(f"  每轮请求: {batch_size} 部")
    print(f"  计划轮次: {rounds} 轮")
    print(f"  模型: {config.model}")
    if prefer_region:
        print(f"  偏好地区: {prefer_region}")
    if prefer_type:
        print(f"  偏好类型: {prefer_type}")
    if prefer_language:
        print(f"  偏好语言: {prefer_language}")
    print()

    for round_idx in range(1, rounds + 1):
        remaining = total - len(all_new_books)
        this_batch = min(batch_size, remaining)
        if this_batch <= 0:
            break

        print(f"\n{'─'*60}")
        print(f"  🔄 第 {round_idx}/{rounds} 轮 — 请求 {this_batch} 部")
        print(f"{'─'*60}")

        # 每轮重新加载注册表（因为上一轮可能已更新）
        registry = load_registry(registry_path)
        memory_block = build_memory_block(registry)
        exclusion_list = build_exclusion_list(registry)

        # 构建 scout 专属额外指令
        scout_extra = (
            f"本次是选书侦察模式第 {round_idx}/{rounds} 轮。\n"
            f"你已被要求总共推荐 {total} 部书，当前已选 {len(all_new_books)} 部。\n"
            f"请确保本轮推荐的 {this_batch} 部与前几轮不重复且尽量覆盖不同地区/类型。"
        )
        if extra_instructions:
            scout_extra += f"\n{extra_instructions}"

        user_prompt = build_user_prompt(
            count=this_batch,
            memory_block=memory_block,
            exclusion_list=exclusion_list,
            prefer_region=prefer_region,
            prefer_type=prefer_type,
            prefer_language=prefer_language,
            extra_instructions=scout_extra,
        )

        if dry_run:
            print(f"\n  ═══ 第 {round_idx} 轮 PROMPT ═══")
            if round_idx == 1:
                print("═══ SYSTEM PROMPT ═══")
                print(SYSTEM_PROMPT)
            print("\n═══ USER PROMPT ═══")
            print(user_prompt)
            continue

        # 调用 LLM
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # ── replay 模式：直接读取已保存的 raw 文件 ──
        replay_file = ""
        if replay_raw_dir:
            candidate = os.path.join(replay_raw_dir, f"scout_round{round_idx}_raw.txt")
            if os.path.exists(candidate):
                replay_file = candidate

        if replay_file:
            print(f"  ♻️  从缓存重放（第 {round_idx} 轮）: {replay_file}")
            with open(replay_file, encoding="utf-8") as _f:
                content = _f.read()
        else:
            print(f"  🤖 正在请求 AI 推荐（第 {round_idx} 轮）...")
            try:
                content = call_llm(
                    messages=messages,
                    config=config,
                    temperature=0.7,
                )
            except Exception as e:
                print(f"  ❌ 第 {round_idx} 轮 API 调用失败: {e}")
                print(f"  ⏩ 跳过本轮，继续下一轮...")
                continue

        recommendations = extract_json_from_text(content)
        if not isinstance(recommendations, list):
            print(f"  ❌ 第 {round_idx} 轮解析失败，跳过")
            raw_file = os.path.join(
                os.path.dirname(registry_path),
                f"scout_round{round_idx}_raw.txt",
            )
            os.makedirs(os.path.dirname(raw_file) or ".", exist_ok=True)
            with open(raw_file, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  💾 原始输出已保存: {raw_file}")
            continue

        # 去重
        existing = get_existing_titles(registry)
        round_books = []
        for rec in recommendations:
            title = rec.get("title", "")
            if title in existing:
                print(f"  ⚠️  跳过已有: 《{title}》")
                continue
            # 计算综合评分
            rec["geo_score"] = compute_geo_score(rec)
            rec["auto_grade"] = grade_from_score(rec["geo_score"])
            round_books.append(rec)

        print(f"\n  ✅ 第 {round_idx} 轮获得 {len(round_books)} 部新推荐：")
        for rec in round_books:
            title = rec.get("title", "?")
            score = rec.get("geo_score", 0)
            auto_g = rec.get("auto_grade", "?")
            orig_g = rec.get("grade", "?")
            region = rec.get("geo_region", "?")
            density = rec.get("density_index", "?")
            print(f"    [{auto_g}|{score}分] 《{title}》 {region} 密度:{density}")

        # 立即写入注册表（让下一轮看到）
        for rec in round_books:
            add_book(
                registry,
                title=rec.get("title", ""),
                author=rec.get("author", ""),
                language=rec.get("language", "zh"),
                book_type=rec.get("type", "novel"),
                grade=rec.get("auto_grade", rec.get("grade", "B")),
                geo_region=rec.get("geo_region", ""),
                geo_scope=rec.get("geo_scope", ""),
                era_setting=rec.get("era_setting", ""),
                place_count_estimate=rec.get("place_count_estimate", 0),
                density_index=rec.get("density_index", 0.0),
                reachability_pct=rec.get("reachability_pct", 0),
                route_shape=rec.get("route_shape", "network"),
                reason=rec.get("reason", ""),
                title_en=rec.get("title_en", ""),
                status="recommended",
                extra={
                    "pilgrimage_appeal": rec.get("pilgrimage_appeal", 0),
                    "audience_size": rec.get("audience_size", ""),
                    "geo_added_value": rec.get("geo_added_value", ""),
                    "value_boundary": rec.get("value_boundary", ""),
                    "timeline_needed": rec.get("timeline_needed", False),
                    "geo_score": rec.get("geo_score", 0),
                    "scout_round": round_idx,
                },
            )
        save_registry(registry, registry_path)

        all_new_books.extend(round_books)
        print(f"  💾 注册表已更新 (累计新增 {len(all_new_books)}/{total} 部)")

        # 轮间间隔（避免 rate limit）
        if round_idx < rounds and len(all_new_books) < total:
            print(f"  ⏳ 等待 3 秒后进入下一轮...")
            time.sleep(3)

    if dry_run:
        return []

    # ═══ 最终排名 ═══
    all_new_books.sort(key=lambda b: b.get("geo_score", 0), reverse=True)

    print(f"\n{'═'*60}")
    print(f"🏆 选书侦察完成 · 地图价值排名")
    print(f"{'═'*60}")
    print(f"  共收集 {len(all_new_books)} 部新书\n")

    print(f"  {'排名':>4} {'评分':>5} {'等级':>4} {'书名':<25} {'作者':<12} {'地区':<8} {'密度':>4} {'可达%':>5} {'吸引力':>4} {'路线':<8}")
    print(f"  {'─'*4} {'─'*5} {'─'*4} {'─'*25} {'─'*12} {'─'*8} {'─'*4} {'─'*5} {'─'*4} {'─'*8}")

    for i, book in enumerate(all_new_books, 1):
        title = book.get("title", "?")[:24]
        author = book.get("author", "?")[:11]
        region = book.get("geo_region", "?")[:7]
        score = book.get("geo_score", 0)
        grade = book.get("auto_grade", "?")
        density = book.get("density_index", 0)
        reach = book.get("reachability_pct", 0)
        appeal = book.get("pilgrimage_appeal", 0)
        shape = book.get("route_shape", "?")[:7]
        print(f"  {i:>4} {score:>5.1f} {grade:>4} {title:<25} {author:<12} {region:<8} {density:>4.1f} {reach:>5} {appeal:>4} {shape:<8}")

    # 按等级统计
    s_count = sum(1 for b in all_new_books if b.get("auto_grade") == "S")
    a_count = sum(1 for b in all_new_books if b.get("auto_grade") == "A")
    b_count = sum(1 for b in all_new_books if b.get("auto_grade") == "B")
    print(f"\n  📊 等级分布: S={s_count} / A={a_count} / B={b_count}")

    # 保存排名结果
    ranked_file = os.path.join(
        os.path.dirname(registry_path),
        f"scout_ranked_{int(time.time())}.json",
    )
    with open(ranked_file, "w", encoding="utf-8") as f:
        json.dump(all_new_books, f, ensure_ascii=False, indent=2)
    print(f"  💾 排名结果: {ranked_file}")
    print(f"  💾 注册表: {registry_path} (总计 {len(load_registry(registry_path)['books'])} 部)")

    return all_new_books


def cmd_import(import_file: str, registry_path: str) -> None:
    """导入外部 JSON 推荐结果"""
    with open(import_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("❌ 导入文件必须是 JSON 数组")
        return

    registry = load_registry(registry_path)
    existing = get_existing_titles(registry)

    added = 0
    for rec in data:
        title = rec.get("title", "")
        if title in existing:
            print(f"  ⏭️  跳过已有: 《{title}》")
            continue

        add_book(
            registry,
            title=title,
            author=rec.get("author", ""),
            language=rec.get("language", "zh"),
            book_type=rec.get("type", "novel"),
            grade=rec.get("grade", "B"),
            geo_region=rec.get("geo_region", ""),
            geo_scope=rec.get("geo_scope", ""),
            era_setting=rec.get("era_setting", ""),
            place_count_estimate=rec.get("place_count_estimate", 0),
            density_index=rec.get("density_index", 0.0),
            reachability_pct=rec.get("reachability_pct", 0),
            route_shape=rec.get("route_shape", "network"),
            reason=rec.get("reason", ""),
            title_en=rec.get("title_en", ""),
            status=rec.get("status", "recommended"),
        )
        added += 1
        print(f"  ✅ 添加: 《{title}》")

    save_registry(registry, registry_path)
    print(f"\n  💾 导入完成: 新增 {added} 部，总计 {len(registry['books'])} 部")


def cmd_mark(title: str, status: str, registry_path: str) -> None:
    """修改某本书的状态"""
    registry = load_registry(registry_path)
    found = False
    for b in registry.get("books", []):
        if b.get("title") == title:
            old_status = b.get("status")
            b["status"] = status
            found = True
            print(f"  ✅ 《{title}》: {old_status} → {status}")
            break

    if not found:
        print(f"  ❌ 未找到书目: 《{title}》")
        return

    save_registry(registry, registry_path)


# ─────────────────────────── Main ─────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="故实巡礼 · AI 选书推荐（带记忆系统）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 推荐 5 本新书（单次模式）
  python scripts/recommend_books.py --count 5

  # 选书侦察模式：推荐 20 本，每轮 5 本，共 4 轮 API 调用
  python scripts/recommend_books.py --mode scout --count 20

  # 选书侦察 + 偏好日本和欧洲的游记
  python scripts/recommend_books.py --mode scout --count 15 --prefer-region "日本,欧洲" --prefer-type "travelogue"

  # 选书侦察 + 自定义每轮数量
  python scripts/recommend_books.py --mode scout --count 30 --batch-size 5

  # 偏好日本和欧洲的游记（单次）
  python scripts/recommend_books.py --count 10 --prefer-region "日本,欧洲" --prefer-type "travelogue"

  # 只打印 prompt（手动使用）
  python scripts/recommend_books.py --dump-prompt --count 5

  # 导入外部推荐结果
  python scripts/recommend_books.py --import-file recs.json

  # 查看注册表
  python scripts/recommend_books.py --status

  # 标记某书为已完成
  python scripts/recommend_books.py --mark "繁花" --set-status completed
        """,
    )

    # 模式
    parser.add_argument("--mode", choices=["recommend", "scout"], default="recommend",
                        help="运行模式: recommend=单次推荐(默认), scout=选书侦察(多轮API+排名)")
    parser.add_argument("--status", action="store_true", help="查看注册表状态")
    parser.add_argument("--dump-prompt", action="store_true", help="只打印 prompt，不调用 API")
    parser.add_argument("--import-file", help="导入外部 JSON 推荐结果")
    parser.add_argument("--mark", help="修改某本书的状态（配合 --set-status）")
    parser.add_argument("--set-status", choices=["recommended", "processing", "completed", "skipped"])

    # 推荐参数
    parser.add_argument("--count", type=int, default=5, help="推荐数量 (默认: 5)")
    parser.add_argument("--batch-size", type=int, default=5, help="scout 模式每轮推荐数量 (默认: 5)")
    parser.add_argument("--replay-raw", default="", metavar="DIR",
                        help="重放指定目录下的 scout_roundN_raw.txt 文件，无需重新调用 API")
    parser.add_argument("--prefer-region", default="", help="偏好地区，逗号分隔")
    parser.add_argument("--prefer-type", default="", help="偏好类型，逗号分隔")
    parser.add_argument("--prefer-language", default="", help="偏好语言，逗号分隔")
    parser.add_argument("--extra", default="", help="额外指令")
    parser.add_argument("--auto-pipeline", action="store_true", help="推荐后自动进入 pipeline")

    # API 配置
    parser.add_argument("--provider", choices=["gemini", "claude"], default="gemini",
                        help="AI 供应商: gemini(默认) 或 claude")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--model", default="", help="模型名称（留空则根据 provider 自动选择）")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY, help="注册表路径")

    args = parser.parse_args()

    # 根据 provider 自动选择模型（如果未指定）
    if not args.model:
        args.model = MODEL_CLAUDE if args.provider == "claude" else MODEL_PRO

    # 分发命令
    if args.status:
        cmd_status(args.registry)
        return

    if args.import_file:
        cmd_import(args.import_file, args.registry)
        return

    if args.mark:
        if not args.set_status:
            print("❌ --mark 需要配合 --set-status")
            sys.exit(1)
        cmd_mark(args.mark, args.set_status, args.registry)
        return

    # 推荐模式 / 侦察模式
    # 注意：API Key 可以从配置文件读取，不一定需要命令行参数
    config = load_llm_config(
        provider=PROVIDER_CLAUDE if args.provider == "claude" else PROVIDER_GEMINI,
        api_key=args.api_key if args.api_key else None,
        base_url=args.base_url or None,
        model=args.model,
        max_tokens=8192,
        timeout=120,
    )

    # 检查是否成功加载了 API Key
    if not args.dump_prompt and not config.api_key:
        print("❌ 需要 API Key: --api-key 或环境变量 GEOLORE_API_KEY 或配置文件 .ai_config.json")
        print("   或使用 --dump-prompt 只打印 prompt")
        sys.exit(1)

    if args.mode == "scout":
        cmd_scout(
            total=args.count,
            config=config,
            registry_path=args.registry,
            prefer_region=args.prefer_region,
            prefer_type=args.prefer_type,
            prefer_language=args.prefer_language,
            extra_instructions=args.extra,
            batch_size=args.batch_size,
            dry_run=args.dump_prompt,
            replay_raw_dir=args.replay_raw,
        )
    else:
        cmd_recommend(
            count=args.count,
            config=config,
            registry_path=args.registry,
            prefer_region=args.prefer_region,
            prefer_type=args.prefer_type,
            prefer_language=args.prefer_language,
            extra_instructions=args.extra,
            dump_prompt=args.dump_prompt,
            auto_pipeline=args.auto_pipeline,
        )


if __name__ == "__main__":
    main()
