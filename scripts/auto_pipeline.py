#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
故实巡礼 · AI 全自动内容生产流水线

流程：
  Step 1: [Pro+Search]  AI 选题 — 选出适合地理化的作品
  Step 2: [Pro+Search]  搜索原文 — 搜索作品梗概/章节信息
  Step 3: [Flash+Search] 批量提取 — 逐批提取地点数据
  Step 4: [Flash]        结构化 — 富化 + Synopsis 生成
  Step 5: [Flash]        质量自审 — 自动审查 + 修复
  Step 6: 输出 places_structured.json → 送入 geocode

用法：
  # AI 自主选题并生成内容（模式 D）
  python scripts/auto_pipeline.py --mode select --count 5

  # 指定作品（模式 C）
  python scripts/auto_pipeline.py --mode specify --work "繁花" --author "金宇澄"

  # 从已有选题文件继续
  python scripts/auto_pipeline.py --mode resume --topics-file output/topics.json

环境变量：
  GEOLORE_API_KEY: API 密钥
  GEOLORE_BASE_URL: API 基础 URL (默认 https://token-plan-cn.xiaomimimo.com/v1)
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import time
import re
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# 添加项目根目录到 path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.common.config import LLMConfig, load_llm_config, MODEL_PRO
from src.common.llm_client import call_llm
from src.common.json_utils import extract_json_from_text

try:
    from src.memory.book_registry import (
        load_registry,
        save_registry,
        add_book,
        build_memory_block,
        build_exclusion_list,
        get_existing_titles,
    )
    HAS_REGISTRY = True
except ImportError:
    HAS_REGISTRY = False

try:
    from src.textsource.fetcher import fetch_full_text, TextResult
    HAS_TEXT_SOURCE = True
except ImportError:
    HAS_TEXT_SOURCE = False

try:
    from src.tracking.tracker import PipelineTracker
    HAS_TRACKER = True
except ImportError:
    HAS_TRACKER = False

# ─────────────────────────── Config ───────────────────────────

DEFAULT_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
DEFAULT_REGISTRY_PATH = "output/data/registry.json"


# ─────────────────────────── Prompts ──────────────────────────

TOPIC_SELECTION_PROMPT = """你是「故实巡礼」的选题编辑。故实巡礼是一款将文学作品中的地点提取为地理坐标，让用户实地巡礼的应用。

任务：选出 {count} 部最适合"地理化"的文学作品（中英文皆可，优先选择受众广泛的）。

═══ 记忆系统（严禁推荐以下书目）═══
{memory_block}
严禁推荐的书目列表：{exclusion_list}
═══════════════════════════════════

选题标准（量化评估）：
1. 地点密度指数 = 预估可提取真实地点数 ÷ 总万字数。≥5 优秀，3-5 良好，<1 不推荐
2. 现实可达率 = 今天仍可到达的地点占比。≥80% 优秀
3. 路线形态：线状（游记/传记/旅途小说）> 网状（城市小说）> 点状（诗集）
4. 巡礼吸引力：读者是否会因为这本书想去实地打卡？

选题偏好：
- 优先选择不同城市/地区的作品，覆盖面要广
- 优先选择有明确真实地名的作品
- 类型要多样：城市小说、游记、传记、历史纪实都要有
- 不要选已经被广泛地图化的作品（如红楼梦等过于经典的）
- 优先选当代/近现代作品（地点可达性更高）
- 主动填充记忆系统中显示的未覆盖地区和类型
- 中英文比例大约 6:4

输出要求：
必须输出一个 JSON 数组，每个元素包含：
{{
  "rank": 排名（1开始）,
  "title": "作品名（原文）",
  "title_en": "英文名/英文原名",
  "author": "作者",
  "language": "zh|en|ja|fr|...",
  "type": "novel|travelogue|biography|poetry|history|folklore|essay",
  "era_setting": "故事发生的时代背景",
  "geo_region": "主要地理区域标签",
  "geo_scope": "地理范围描述",
  "word_count_estimate": 估算万字数（数字）,
  "place_count_estimate": 预估可提取地点数（数字）,
  "density_index": 地点密度指数（保留1位小数）,
  "reachability_pct": 现实可达率（0-100整数）,
  "route_shape": "linear|network|scattered",
  "timeline_needed": true/false,
  "grade": "S|A|B",
  "reason": "50字以内的选择理由"
}}

只输出 JSON 数组，不要其他内容。"""


SEARCH_WORK_PROMPT = """你是文学研究助手。请搜索并整理以下作品的详细信息：

作品：《{title}》，作者：{author}

请搜索并提供：
1. 作品简介（200字以内）
2. 主要故事线/情节概要（按章节或情节推进顺序）
3. 故事的时间线（如果有明确时间）

关于地名，请 **严格区分** 以下两类，分开列出：

【A 类：原著文本中明确出现的地名】
原著中白纸黑字写出的真实地名。引用原文中的相关句子作为证据。
⚠️ 注意：有些小说（如《围城》）故意模糊地名，只用城市名而不写具体街道/建筑。
   如果原著只写"上海"，就只列"上海"，不要补充"外滩""霞飞路"等具体地标。

【B 类：学术考证/推测的原型地】
学者、注释、后记中考证出的原型地点。必须标注出处（如"据杨绛《记钱钟书与围城》"）。
这类地点不是原著文字，而是研究者的推断。

请对每个地名标注属于 A 类还是 B 类。"""


EXTRACT_PLACES_PROMPT = """你是「故实巡礼」的地点提取引擎。

作品：《{title}》，作者：{author}
作品类型：{work_type}，时代背景：{era_setting}，地理范围：{geo_scope}

以下是这部作品的 **原文片段**（全书已按章节分块，这是其中一块）：
---
{work_info}
---

任务：仔细阅读上面这段原文，提取其中所有真实、可巡礼的地理位置。

━━━ 核心原则（最高优先级）━━━
⚠️ 只提取本段原文中 **白纸黑字写出** 的真实地名。
⚠️ 不得凭你对时代背景、城市地标的"常识"自行补充地点。
⚠️ 如果原文只写了城市名（如"Suez"、"上海"），不要自行细化到具体街道/建筑。
⚠️ 如果这段原文中没有明确地名，输出空数组 [] 即可——宁缺毋滥。
⚠️ 每个地点必须引用原文中的对应文字作为 source_evidence。

提取规则：
1. 只提取现实世界中真实存在（或曾经存在）的地点
2. 完全虚构的地名标记 fictional_suspect: true
3. address 格式：国家-省-市-区/县-具体地点（尽量精确到街道/建筑级别）
   · 中国地址示例：中国-北京-北京-西城区-椿树胡同
   · 国际地址示例：England-London-Pall Mall-Reform Club
4. 同一地点在本段中出现多次时合并为一条，综合所有情节
5. source_evidence 必须是原文中的直接引用（复制原文原句），不是你的总结

角色名称规则：
⚠️ characters 中的人物名称必须使用角色真名，不要用"我""narrator"等代词。
⚠️ 第一人称叙述者请推断其真名（如小说中"我"就是"英子"）。
⚠️ 同一人物只用一个名称（如"英子"不要有时写"林英子"）。

输出 JSON 数组，每个元素：
{{
  "title": "地点核心名称（原文语言）",
  "address": "国家-省-市-区-具体地点",
  "story": "该地点在本段原文中的具体情节，≤100字，中文",
  "source_evidence": "原文原句引用",
  "chapter_hint": "所在章节标题或编号（如有）",
  "original_chapter": "原著目录中的章节名（如'惠安馆'、'Chapter 3'）",
  "event_level": "major|minor|passing",
  "characters": ["角色真名"],
  "fictional_suspect": false
}}

只输出 JSON 数组。提取本段中的所有地点，宁缺毋滥。"""


ENRICH_PLACES_PROMPT = """你是「故实巡礼」的数据结构化引擎与故事模式生成器。

作品：《{title}》，作者：{author}，类型：{work_type}
时代背景：{era_setting}

{global_context}

以下是本批需要处理的地点数据（JSON 数组）：
{places_json}

━━━ 核心原则（最高优先级）━━━
⚠️ 你只能对输入的地点进行结构化富化，**绝对不能新增、替换或删除地点**。
⚠️ 所有内容必须基于该地点在 **原著中的具体情节**，不得虚构原著中没有的场景。
⚠️ 如果某个地点在原著中的情节较少，narrative_text 可以简短（下限100字），不要编造情节。

━━━ 任务一：结构化富化 ━━━

对每个地点执行：
(a) synopsis：≤80字摘要（第三人称，中文，抓核心故事点），用于地图卡片预览
(b) 保留并补全 source_evidence：必须是原著原文引用（原文语言），不得改写
(c) 时空语境 temporal_context：
    - era: 时代背景
    - historical_name: 古地名/旧称（无则 null）
    - date_start / date_end: 故事发生时间（YYYY 格式，不确定可留空）
(d) 叙事语境 narrative_context：
    - event_level: major/minor/passing
    - characters: 该地点关联人物（⚠️ 必须遵守角色统一规则）
    - stay_duration: 人物在此停留时长
(e) 文化标签 cultural_tags：
    - category: literary_site|historical_site|travelogue|biographical|architectural|natural_landscape|culinary|religious|folklore
    - themes: 英文主题标签数组（如 ["adventure","wager"]）
    - significance: 0.00-1.00（major=0.7-1.0, minor=0.4-0.7, passing=0.1-0.4）
(f) 原著篇章映射 original_chapter：
    - 该地点对应原著的哪个篇章/章节名（原书目录中的名称）
    - 如原著分为多个独立故事/篇章，必须标注属于哪个 part
    - 格式：原著章节名字符串，如 "惠安馆"、"我们看海去"、"Chapter 3" 等
(g) 打卡可行性 visitability：
    - status: "exists" | "demolished" | "relocated" | "uncertain"
      · exists = 该地点今天仍然存在且可到达
      · demolished = 已拆除/消失
      · relocated = 已搬迁到新地址
      · uncertain = 不确定是否还在
    - note: 简短说明（如 "原址已改建为XX"、"现为XX公园"），无则 null
    - current_name: 如果今名与文中名称不同，写今天的名称，否则 null

━━━ 任务二：角色统一规则（极重要）━━━

⚠️ 同一个人物在所有地点中必须使用 **完全相同的名称**。
  1. 第一人称叙述者（"我"）→ 使用角色真名（如 "英子" 不是 "我" 或 "林英子"）
  2. 同一人物的不同称呼 → 统一为最常用的那个，全局一致
  3. 泛指角色（如 "同学""邻居"）→ 除非有具体行为，否则不列入
  4. 本批与前后批次保持一致（参考全局上下文中的角色名）

━━━ 任务三：篇章(Part)划分 ━━━

许多文学作品由多个独立故事/篇章组成。
你必须为每个地点标注它属于哪个 part：
  part_id: "PART-1" | "PART-2" | ...（按出场顺序编号）
  part_title: 该篇章的原著标题（如 "惠安馆"、"我们看海去"）

如果作品不分 part（单一连续长篇），则 part_id 统一为 "PART-1"。

story_mode 中的 chapter_title 编号在每个 part 内从 1 重新开始。

━━━ 任务四：故事排序 ━━━

orderIndex 从 {order_offset} 开始递增，按故事情节出场顺序排列。
排序逻辑：小说按情节推进顺序，游记按行程，传记按时间线。

━━━ 任务五：故事模式（Story Mode）━━━

为每个地点生成 story_mode，让用户按节点顺序阅读时能体验完整故事。

🎯 核心目标：一个完全没有读过原著的人，只通过按顺序阅读所有地点的 story_mode，
就能理解整个故事的起承转合、人物关系和情感脉络。

(i) chapter_title — 格式 "第X章·[生动标题]"，X 在 part 内从 1 编号
(ii) hook — 悬念钩子（≤30字），制造好奇心
(iii) narrative_text — 沉浸式叙事（100-350字）：
    · 第三人称文学性叙述，与原著风格一致
    · 【关键】必须基于原著中在该地点实际发生的情节
    · 【新读者友好】人物首次出场时，用1-2句话自然交代其身份/关系
      （如 "秀贞——惠安馆里那个被邻居们叫作疯子的年轻女人" 而非直接写 "秀贞"）
    · 每个 part 的第一个地点应有简短的篇章背景引入
    · 有情节推进、环境氛围、情感温度
(iv) transition_to — 过渡语（≤50字），自然引向下一地点。
     跨 part 时应暗示旧篇章结束和新篇章开始。本批最后一个写"（待续）"
(v) mood — 情绪标签：tense/nostalgic/joyful/melancholic/dramatic/peaceful/mysterious/bittersweet/ambitious/desolate
(vi) key_dialogue — 原著中的台词或描写引用（原文语言），如无合适引用则为 null

━━━ 任务六：地址精确化（为地理编码准备）━━━

address 的精度直接决定地图打卡能否定位。请遵循：
  1. 中国地址：中国-省-市-区/县-具体街道/胡同/建筑
     示例：中国-北京-北京-西城区-椿树胡同
  2. 国际地址：国家-城市-具体地点
  3. 必须精确到街道/建筑级别，绝不能只写到区级
  4. 已不存在的地点：address 写原址位置，visitability.status 标注 demolished

输出 JSON 数组，每个元素：
{{
  "title": "地点名称",
  "address": "国家-省-市-区-具体地点",
  "synopsis": "≤80字摘要",
  "source_evidence": "原著原文引用",
  "original_chapter": "原著章节名",
  "part_id": "PART-1",
  "part_title": "篇章标题",
  "temporal_context": {{
    "era": "时代",
    "historical_name": null,
    "date_start": "YYYY",
    "date_end": "YYYY"
  }},
  "narrative_context": {{
    "event_level": "major|minor|passing",
    "characters": ["统一角色名"],
    "stay_duration": "时长描述"
  }},
  "cultural_tags": {{
    "category": "literary_site",
    "themes": ["tag1", "tag2"],
    "significance": 0.85
  }},
  "visitability": {{
    "status": "exists|demolished|relocated|uncertain",
    "note": "简短说明或null",
    "current_name": "今名或null"
  }},
  "timeline": {{
    "orderIndex": {order_offset},
    "dateStart": "YYYY",
    "dateEnd": "YYYY"
  }},
  "story_mode": {{
    "chapter_title": "第1章·[标题]",
    "hook": "≤30字悬念钩子",
    "narrative_text": "100-350字沉浸叙事",
    "transition_to": "≤50字过渡语",
    "mood": "peaceful",
    "key_dialogue": "原著引用或null"
  }}
}}

只输出 JSON 数组。保持地点数量不变。按 orderIndex 升序排列。"""


REVIEW_PROMPT = """你是「故实巡礼」的质量审查引擎。

作品：《{title}》，作者：{author}

以下是全部地点数据（已结构化，含 story_mode）：
{places_json}

━━━ 第一优先级：原著忠实性检查 ━━━
逐个审查每个地点，用 source_evidence 判断：
1. 该地点是否在《{title}》原著中被 **明确提及**？
   - source_evidence 是否看起来是原著原文？（不是 AI 编造的）
   - 如果某地点只是该城市的著名地标，但 source_evidence 无法确认原著提及 → 移除
2. narrative_text 是否基于原著情节？是否虚构了原著没有的场景？
   - 如果 narrative_text 编造了明显不属于原著的情节 → 重写，只保留原著有据可查的内容
   - 如果情节较少导致 narrative_text 短也没关系（下限100字），不要编造

━━━ 第二优先级：角色名统一性检查 ━━━
3. 检查所有地点的 characters 数组：
   - 同一人物是否使用了不同名称？（如 "英子"/"林英子"/"我"）→ 统一为最常用的一个
   - 第一人称叙述者是否用了代词（"我"）？→ 替换为角色真名
   - 列出所有唯一角色名，确认无重复指向

━━━ 第三优先级：数据质量 ━━━
4. 重复地点（同一真实地点不同叫法）→ 合并
5. address 精度检查：
   - 至少含 3 级（如 "中国-北京-西城区-椿树胡同"）→ 不足则补全
   - 不能只到区级（如 "中国-北京-海淀区"）→ 必须有具体地点名
6. synopsis ≤80字、第三人称 → 超长截断
7. significance 与 event_level 匹配 → 修正
8. visitability 检查：每个地点必须有 visitability 字段 → 缺失则补充
9. part_id / part_title / original_chapter 检查 → 缺失则补充

━━━ 第四优先级：故事模式连贯性 ━━━
10. orderIndex 重新编号：从 1 连续递增，按故事推进顺序排列
11. chapter_title 格式 "第X章·[标题]"，X 在每个 part 内从 1 编号
12. 按新顺序读 transition_to → 每个应自然指向下一地点
    - 跨 part 的 transition_to 应暗示篇章转换
    - 最后一个写总结性结束语
13. mood 序列应有起伏变化，不能全部相同
14. hook ≤30字，要有悬念感
15. 新读者可读性：narrative_text 中人物首次出场是否有身份交代？

━━━ 第五优先级：passing 级地点降噪 ━━━
16. 对于 event_level=passing 且 significance<0.25 的地点：
    - 如果 story_mode.narrative_text 中没有实质性情节（只是"路过"）→ 考虑移除
    - 保留标准：该地点是否对理解故事线有帮助？是否有打卡价值？
    - 移除后确保 transition_to 链条不断裂

━━━ 输出要求 ━━━
输出修复后的完整 JSON 数组（格式与输入一致）。
被移除的地点直接删掉（不要输出）。
在数组最后追加一个审查报告元素：
{{
  "_review_report": true,
  "total": 最终保留总数,
  "removed_not_in_original": 因原著证据不足移除的数量,
  "removed_fictional": 移除的虚构地名数,
  "removed_low_value": 移除的低价值passing地点数,
  "removed_names": ["被移除的地点名称列表"],
  "merged_duplicates": 合并的重复地点数,
  "fixed_address": 修复地址数,
  "fixed_synopsis": 修复synopsis数,
  "fixed_narrative": 重写narrative数,
  "fixed_characters": 统一角色名的修复数,
  "character_roster": ["最终的全局角色名列表"],
  "parts_found": ["PART-1: 篇章标题", "PART-2: 篇章标题"],
  "reindexed": true,
  "mood_arc": ["按orderIndex顺序的mood列表"],
  "story_mode_enabled": true,
  "avg_narrative_length": 平均narrative_text字数,
  "transition_coverage": "有transition的地点数/总数"
}}

只输出 JSON 数组。"""


# ─────────────────────────── Pipeline Steps ───────────────────

BOOK_META_PROMPT = """你是「故实巡礼」的图书元数据生成引擎。

作品：《{title}》，作者：{author}，类型：{work_type}
时代背景：{era_setting}

以下是从这部作品中提取到的所有地点数据（已结构化）：
{places_summary}

━━━ 任务 ━━━

基于你对这部作品的理解和上面的地点数据，生成以下三块元数据。
这些数据将作为"封面"和"目录"展示给用户——尤其是从没读过这本书的用户。

━━━ 1. 全书简介 book_summary ━━━
为从未读过这本书的人写一段简介（150-250字，中文）。
要求：
- 点明作者、时代背景、核心主题
- 不要剧透关键结局，但要让人想读
- 说明这本书的地理特色（如"故事发生在1920年代的老北京城南"）
- 语气温暖，有文学感，不要百科式

━━━ 2. 角色表 characters ━━━
列出作品中所有重要角色。这对新读者至关重要。
每个角色包含：
- id: 全局唯一标识（如 "yingzi"、"xiuzhen"），小写英文
- name: 角色名称（必须与地点数据中 characters 数组里的名称完全一致）
- aliases: 同一角色的其他称呼数组（如 ["林英子", "我"]），用于下游角色合并
- role: 角色身份/关系的一句话描述（如"故事的主角，一个住在城南的小女孩"）
- first_appearance: 该角色首次出场的地点 title
- importance: "protagonist" | "major" | "supporting" | "minor"

⚠️ 关键：name 字段必须与地点数据 characters 数组中使用的名称完全匹配。
⚠️ 如果地点数据中同一人物出现了不同名称（如"英子"和"林英子"），
   选最常用的作为 name，其余放入 aliases。

━━━ 3. 篇章结构 parts ━━━
列出作品的篇章/Part 划分。
每个 part 包含：
- part_id: "PART-1"、"PART-2"...
- title: 篇章标题（原著章节名）
- synopsis: 该篇章的简短摘要（≤60字）
- place_count: 该篇章包含的地点数量
- mood: 该篇章的主要情绪基调
- key_characters: 该篇章的核心人物

如果作品没有明确的篇章划分（单一长篇），则只输出一个 PART-1。

━━━ 输出格式（严格 JSON）━━━
{{
  "book_summary": "150-250字全书简介",
  "characters": [
    {{
      "id": "yingzi",
      "name": "英子",
      "aliases": ["林英子", "我"],
      "role": "故事主角，住在城南的小女孩",
      "first_appearance": "惠安馆",
      "importance": "protagonist"
    }}
  ],
  "parts": [
    {{
      "part_id": "PART-1",
      "title": "惠安馆",
      "synopsis": "≤60字摘要",
      "place_count": 14,
      "mood": "nostalgic",
      "key_characters": ["英子", "秀贞", "妞儿"]
    }}
  ]
}}

只输出 JSON 对象。"""


def step0_select_topics(config: LLMConfig, count: int, registry_path: str = DEFAULT_REGISTRY_PATH) -> List[Dict]:
    """Step 0: AI 自主选题（带记忆防重复）"""
    print(f"\n{'='*60}")
    print(f"📋 Step 0: AI 选题（选 {count} 部作品）")
    print(f"   模型: {MODEL_PRO}")

    # 加载记忆
    memory_block = "（暂无已处理书籍，这是第一次选题。）"
    exclusion_list = ""
    if HAS_REGISTRY:
        registry = load_registry(registry_path)
        memory_block = build_memory_block(registry)
        exclusion_list = build_exclusion_list(registry)
        existing_count = len(registry.get("books", []))
        print(f"   记忆: 已有 {existing_count} 部书目")
    else:
        print(f"   记忆: （未加载 registry 模块）")

    print(f"{'='*60}")

    prompt = TOPIC_SELECTION_PROMPT.format(
        count=count,
        memory_block=memory_block,
        exclusion_list=exclusion_list,
    )
    content = call_llm(
        messages=[{"role": "user", "content": prompt}],
        config=config,
        model=MODEL_PRO,
        temperature=0.7,
    )

    topics = extract_json_from_text(content)
    if not isinstance(topics, list):
        print(f"  ❌ 解析失败，原始输出:\n{content[:500]}")
        return []

    # 二次去重：检查 AI 是否仍然推荐了已有书目
    if HAS_REGISTRY:
        existing_titles = get_existing_titles(registry)
        original_count = len(topics)
        topics = [t for t in topics if t.get("title", "") not in existing_titles]
        if len(topics) < original_count:
            print(f"  ⚠️  过滤掉 {original_count - len(topics)} 部已有书目")

    print(f"  ✅ 选出 {len(topics)} 部作品：")
    for t in topics:
        grade = t.get("grade", "?")
        title = t.get("title", "?")
        author = t.get("author", "?")
        lang = t.get("language", "zh")
        density = t.get("density_index", "?")
        reach = t.get("reachability_pct", "?")
        print(f"     [{grade}级] 《{title}》{author} | {lang} | 密度:{density} 可达:{reach}%")

    # 将选题结果写入 registry
    if HAS_REGISTRY:
        for t in topics:
            add_book(
                registry,
                title=t.get("title", ""),
                author=t.get("author", ""),
                language=t.get("language", "zh"),
                book_type=t.get("type", "novel"),
                grade=t.get("grade", "B"),
                geo_region=t.get("geo_region", ""),
                geo_scope=t.get("geo_scope", ""),
                era_setting=t.get("era_setting", ""),
                place_count_estimate=t.get("place_count_estimate", 0),
                density_index=t.get("density_index", 0.0),
                reachability_pct=t.get("reachability_pct", 0),
                route_shape=t.get("route_shape", "network"),
                reason=t.get("reason", ""),
                title_en=t.get("title_en", ""),
                status="recommended",
            )
        save_registry(registry, registry_path)
        print(f"  💾 选题已同步到注册表: {registry_path}")

    return topics


def step0b_fetch_text(
    title: str, author: str, language: str = "", cache_dir: str = "output/.text_cache"
) -> Optional[str]:
    """Step 0b: 从开放文学数据库获取原文（全文获取层）
    
    在 LLM 搜索之前，先尝试从 Gutenberg / Wikisource / Open Library
    获取作品全文。有全文时地点提取准确率大幅提升。
    """
    if not HAS_TEXT_SOURCE:
        print(f"\n  ⏭️  原文获取模块未加载，跳过全文获取")
        return None

    print(f"\n{'='*60}")
    print(f"📚 Step 0b: 尝试获取《{title}》原文")
    print(f"   数据源: Gutenberg / Wikisource / Open Library")
    print(f"{'='*60}")

    try:
        result = fetch_full_text(
            title=title,
            author=author,
            language=language,
            cache_dir=cache_dir,
        )
    except Exception as e:
        print(f"  ⚠️  原文获取异常: {e}")
        return None

    if not result:
        print(f"  ℹ️  未找到可用原文，将使用 LLM+Search 模式")
        return None

    print(f"  ✅ {result.summary()}")

    # 保留完整全文，分块逻辑由 step2_extract_places 负责
    text = result.full_text
    print(f"  📄 全文长度: {len(text):,} 字符（Step 2 将分块处理）")

    # 构建带元数据的文本块
    header = (
        f"═══ 原文数据（来源: {result.source}）═══\n"
        f"作品: 《{result.title}》\n"
        f"作者: {result.author}\n"
        f"语言: {result.language}\n"
        f"来源: {result.url}\n"
        f"字数: {result.word_count:,}\n"
        f"类型: {'全文' if result.is_full_text else '摘要/元数据'}\n"
        f"═══════════════════════════════════════\n\n"
    )
    return header + text


def step1_search_work(config: LLMConfig, title: str, author: str) -> str:
    """[DEPRECATED] Step 1: 用 Pro+Search 搜索作品信息。
    已被原文直接提供模式取代，保留此函数仅供参考。"""
    print("⚠️  step1_search_work 已弃用，请使用 --text-file 或自动数据库获取原文")
    print(f"\n{'='*60}")
    print(f"🔍 Step 1: 搜索《{title}》原文/资料")
    print(f"   模型: {MODEL_PRO} (带搜索)")
    print(f"{'='*60}")

    prompt = SEARCH_WORK_PROMPT.format(title=title, author=author)
    content = call_llm(
        messages=[{"role": "user", "content": prompt}],
        config=config,
        model=MODEL_PRO,
        temperature=0.2,
    )

    word_count = len(content)
    print(f"  ✅ 获取到 {word_count} 字的作品资料")

    # 粗略统计提到的地点数
    location_hints = len(re.findall(r'[省市区县镇乡村路街巷桥寺庙塔湖山岭]', content))
    print(f"  📍 资料中包含约 {location_hints} 个地理相关词汇")

    return content


# ── 分块策略：每块包含的章节数
# 先按章节标题将全文精确拆分，再把相邻 N 章合并成一块，绝不劈断章节
STEP2_CHAPTERS_PER_CHUNK = 2

# Step 2 并发数：同时请求多少块（保守设为 2）
STEP2_CONCURRENCY = 2

# 支持的章节标题正则（英文 CHAPTER、中文第X章等）
_CHAPTER_PATTERN = re.compile(
    r'(?m)^(CHAPTER\s+[IVXLCDM\d]+|Chapter\s+[IVXLCDM\d]+|第[零一二三四五六七八九十百千\d]+[章节回])[^\n]*$'
)


def _split_text_into_chunks(
    full_text: str,
    chapters_per_chunk: int = STEP2_CHAPTERS_PER_CHUNK,
) -> List[str]:
    """将全文严格按章节标题切分，每块包含 chapters_per_chunk 章。

    切割规则（按优先级）：
    1. 用正则匹配章节标题行（CHAPTER I / 第一章 等），以此为边界切出每一章
    2. 把相邻 chapters_per_chunk 章合并为一块，绝不在章节中间截断
    3. 若全文找不到任何章节标题，退化为按段落切（兜底）
    每块前面都附带作品元数据 header，方便 LLM 了解背景。
    """
    # ── 提取元数据 header 与正文 body ──
    sep = "═══════════════════════════════════════"
    if sep in full_text:
        parts = full_text.split(sep, 1)
        header_part = parts[0] + sep
        body = parts[1].lstrip("\n") if len(parts) > 1 else full_text
    else:
        header_part = ""
        body = full_text

    # ── 按章节标题切分 ──
    matches = list(_CHAPTER_PATTERN.finditer(body))

    if not matches:
        # 兜底：找不到章节标题，按双空行段落切，每 ~20000 字符一块
        FALLBACK_CHARS = 20000
        raw_chunks = []
        pos = 0
        while pos < len(body):
            end = min(pos + FALLBACK_CHARS, len(body))
            if end < len(body):
                cut = body.rfind("\n\n", pos + FALLBACK_CHARS // 2, end)
                end = cut if cut > pos else end
            raw_chunks.append(body[pos:end])
            pos = end
        return [header_part + "\n" + c if header_part else c for c in raw_chunks]

    # 把 body 切成章节列表：[前言(可能为空), 第1章, 第2章, ...]
    chapter_texts: List[str] = []
    # 章节标题之前的内容（目录、序言等）
    preamble = body[: matches[0].start()].strip()
    if preamble:
        chapter_texts.append(preamble)

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        chapter_texts.append(body[start:end].strip())

    # ── 把相邻 N 章合并为一块 ──
    raw_chunks: List[str] = []
    # 前言单独作为第一块（如果存在且内容够短则并入第一批章节）
    i = 0
    if preamble and chapter_texts and chapter_texts[0] == preamble:
        # 前言并入第一批章节
        i = 0
        chapters_only = chapter_texts[1:]  # 跳过前言
        # 前言 + 前 (chapters_per_chunk-1) 章 作为第一块
        first_batch = [chapter_texts[0]] + chapters_only[: chapters_per_chunk - 1]
        raw_chunks.append("\n\n".join(first_batch))
        remaining = chapters_only[chapters_per_chunk - 1 :]
    else:
        remaining = chapter_texts

    for j in range(0, len(remaining), chapters_per_chunk):
        batch = remaining[j : j + chapters_per_chunk]
        raw_chunks.append("\n\n".join(batch))

    # ── 每块附上 header ──
    return [header_part + "\n\n" + c if header_part else c for c in raw_chunks]


def _merge_dedup_places(all_places: List[Dict]) -> List[Dict]:
    """合并多个分块提取的地点列表，按 title 去重（保留 event_level 最高的版本）"""
    level_rank = {"major": 3, "minor": 2, "passing": 1}
    seen: Dict[str, Dict] = {}  # title -> place

    for p in all_places:
        if not isinstance(p, dict):
            continue
        raw_title = p.get("title", "").strip()
        if not raw_title:
            continue
        # 归一化 key：小写 + 去空格，避免大小写/空格差异导致重复
        key = raw_title.lower().replace(" ", "")
        if key not in seen:
            seen[key] = p
        else:
            # 保留 event_level 更高的版本
            existing_rank = level_rank.get(seen[key].get("event_level", "passing"), 1)
            new_rank = level_rank.get(p.get("event_level", "passing"), 1)
            if new_rank > existing_rank:
                # 新版本级别更高，但保留 source_evidence 更长的那个
                if len(p.get("source_evidence", "")) < len(seen[key].get("source_evidence", "")):
                    p["source_evidence"] = seen[key]["source_evidence"]
                seen[key] = p
            else:
                # 保留旧版本，但合并更丰富的 source_evidence
                if len(p.get("source_evidence", "")) > len(seen[key].get("source_evidence", "")):
                    seen[key]["source_evidence"] = p["source_evidence"]

    return list(seen.values())


def step2_extract_places(
    config: LLMConfig,
    title: str,
    author: str,
    work_type: str,
    era_setting: str,
    geo_scope: str,
    work_info: str,
    min_places: int = 15,
) -> List[Dict]:
    """Step 2: 基于原文提取地点（全文分块，多并发请求后合并去重）"""
    print(f"\n{'='*60}")
    print(f"📍 Step 2: 从原文提取《{title}》的地点")
    print(f"   模型: {MODEL_PRO}")
    print(f"   数据源: 原著全文（分块 + {STEP2_CONCURRENCY} 并发）")
    print(f"{'='*60}")

    # ── 分块 ──────────────────────────────────────────────────
    chunks = _split_text_into_chunks(work_info, STEP2_CHAPTERS_PER_CHUNK)
    total_chunks = len(chunks)
    total_chars = sum(len(c) for c in chunks)
    print(f"  📚 全文 {total_chars:,} 字符 → 按章节切分为 {total_chunks} 块（每块 {STEP2_CHAPTERS_PER_CHUNK} 章）")

    # ── 单块提取函数（供线程池调用）────────────────────────────
    _print_lock = threading.Lock()

    def _extract_one_chunk(chunk_idx: int, chunk_text: str) -> List[Dict]:
        """提取单个分块的地点，失败最多重试 1 次"""
        chunk_label = f"第 {chunk_idx}/{total_chunks} 块"

        prompt = EXTRACT_PLACES_PROMPT.format(
            title=title,
            author=author,
            work_type=work_type,
            era_setting=era_setting,
            geo_scope=geo_scope,
            work_info=chunk_text,
        )

        for attempt in range(1, 3):  # 最多重试 2 次
            content = call_llm(
                messages=[{"role": "user", "content": prompt}],
                config=config,
                model=MODEL_PRO,
                temperature=0.2,
            )
            places_chunk = extract_json_from_text(content)
            if isinstance(places_chunk, list):
                with _print_lock:
                    print(f"  ✅ {chunk_label}（{len(chunk_text):,} 字符）→ {len(places_chunk)} 个地点")
                return places_chunk
            else:
                if attempt < 2:
                    with _print_lock:
                        print(f"  ⚠️  {chunk_label} 解析失败（第 {attempt} 次），重试...")
                    prompt = prompt + "\n\n请确保输出合法的 JSON 数组。"
                else:
                    with _print_lock:
                        print(f"  ❌ {chunk_label} 解析失败，跳过此块")
        return []

    # ── 并发提取 ──────────────────────────────────────────────
    all_raw_places: List[Dict] = []
    print(f"\n  🚀 启动 {min(STEP2_CONCURRENCY, total_chunks)} 并发提取...")
    t0 = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=STEP2_CONCURRENCY) as pool:
        futures = {
            pool.submit(_extract_one_chunk, idx, text): idx
            for idx, text in enumerate(chunks, 1)
        }
        # 按完成顺序收集，但最终按原始 chunk 顺序排列以保持去重一致性
        results_by_idx: Dict[int, List[Dict]] = {}
        for future in concurrent.futures.as_completed(futures):
            idx = futures[future]
            try:
                results_by_idx[idx] = future.result()
            except Exception as exc:
                with _print_lock:
                    print(f"  ❌ 第 {idx}/{total_chunks} 块出错: {exc}")
                results_by_idx[idx] = []

    # 按原始顺序合并
    for idx in sorted(results_by_idx.keys()):
        all_raw_places.extend(results_by_idx[idx])

    elapsed = time.time() - t0
    print(f"\n  ⏱️  并发提取完成，耗时 {elapsed:.1f}s（{total_chunks} 块 / {STEP2_CONCURRENCY} 并发）")

    # ── 合并去重 ──────────────────────────────────────────────
    merged = _merge_dedup_places(all_raw_places)
    print(f"  🔀 合并去重: {len(all_raw_places)} 条原始 → {len(merged)} 条唯一地点")

    # 过滤掉 fictional_suspect
    valid = [p for p in merged if not p.get("fictional_suspect", False)]
    suspect = [p for p in merged if p.get("fictional_suspect", False)]

    print(f"  ✅ 最终提取 {len(merged)} 个地点（有效: {len(valid)}, 疑似虚构: {len(suspect)}）")

    # 按 event_level 统计
    levels = {}
    for p in valid:
        lvl = p.get("event_level", "unknown")
        levels[lvl] = levels.get(lvl, 0) + 1
    for lvl, cnt in sorted(levels.items()):
        print(f"     {lvl}: {cnt} 个")

    return merged


def step3_enrich_places(
    config: LLMConfig,
    title: str,
    author: str,
    work_type: str,
    era_setting: str,
    places: List[Dict],
) -> List[Dict]:
    """Step 3: 结构化 + 故事模式生成（分批处理，传递全局上下文）"""
    print(f"\n{'='*60}")
    print(f"✨ Step 3: 结构化富化 + 故事模式（{len(places)} 个地点）")
    print(f"   模型: {MODEL_PRO}（纯结构化，无搜索）")
    print(f"{'='*60}")

    BATCH_SIZE = 6      # 每批地点数
    STEP3_CONCURRENCY = 5  # Step3 并发线程数（Gemini Flash 容量较大）

    # 构建全地点标题列表（给 LLM 全局视角）
    all_titles = [p.get("title", "?") for p in places]
    total_batches = (len(places) + BATCH_SIZE - 1) // BATCH_SIZE

    # ── 预先为每批构建 prompt（上下文基于 places 输入，不依赖前批返回结果）──
    batch_tasks: List[Tuple[int, List[Dict], str]] = []  # (batch_idx, batch, prompt)
    for i in range(0, len(places), BATCH_SIZE):
        batch = places[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        order_offset = i + 1  # orderIndex 基于输入位置计算，无需串行依赖

        ctx_parts = []
        ctx_parts.append(f"全书共提取了 {len(places)} 个地点，当前是第 {batch_num}/{total_batches} 批。")
        ctx_parts.append(f"完整地点顺序: {' → '.join(all_titles)}")

        # 上一批最后一个地点（直接从 places 输入中取，不依赖前批 API 返回）
        if i > 0:
            prev_title = places[i - 1].get("title", "?")
            ctx_parts.append(
                f"上一批最后的地点是 \"{prev_title}\"。"
                f"请让本批第一个地点的叙事自然承接。"
            )
        if i + BATCH_SIZE < len(places):
            next_title = places[i + BATCH_SIZE].get("title", "?")
            ctx_parts.append(f"本批之后下一个地点是 \"{next_title}\"，请让最后一个 transition_to 指向它。")
        else:
            ctx_parts.append("这是最后一批，最后一个地点的 transition_to 应写总结性结束语。")

        global_context = "\n".join(ctx_parts)

        prompt = ENRICH_PLACES_PROMPT.format(
            title=title,
            author=author,
            work_type=work_type,
            era_setting=era_setting,
            global_context=global_context,
            order_offset=order_offset,
            places_json=json.dumps(batch, ensure_ascii=False, indent=2),
        )
        batch_tasks.append((batch_num, batch, prompt))

    # ── 单批次执行函数 ──
    def _enrich_one_batch(task: Tuple[int, List[Dict], str]) -> Tuple[int, List[Dict]]:
        batch_num, batch, prompt = task
        try:
            content = call_llm(
                messages=[{"role": "user", "content": prompt}],
                config=config,
                model=MODEL_PRO,
                temperature=0.2,
                expect_json=True,
                max_tokens=4096,
            )
        except Exception as e:
            print(f"     ⚠️  批次 {batch_num}/{total_batches} API 调用失败（{e}），保留原始数据")
            return (batch_num, batch)

        enriched = extract_json_from_text(content)
        if isinstance(enriched, list):
            print(f"     ✅ 批次 {batch_num}/{total_batches} 返回 {len(enriched)} 个结构化地点")
            return (batch_num, enriched)
        elif isinstance(enriched, dict) and "places" in enriched:
            items = enriched["places"]
            print(f"     ✅ 批次 {batch_num}/{total_batches} 返回 {len(items)} 个结构化地点（unwrapped）")
            return (batch_num, items)
        else:
            print(f"     ⚠️  批次 {batch_num}/{total_batches} 解析失败，保留原始数据")
            if content:
                print(f"     DEBUG: 返回内容前 200 字: {content[:200]}")
            return (batch_num, batch)

    # ── 并发执行所有批次，结果按 batch_num 排序后顺序合并 ──
    print(f"  🚀 并发执行 {total_batches} 个批次（{STEP3_CONCURRENCY} 线程）")
    results: List[Tuple[int, List[Dict]]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=STEP3_CONCURRENCY) as executor:
        futures = {executor.submit(_enrich_one_batch, task): task[0] for task in batch_tasks}
        for future in concurrent.futures.as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                batch_num = futures[future]
                print(f"     ❌ 批次 {batch_num} 线程异常: {e}，保留原始数据")
                original_batch = batch_tasks[batch_num - 1][1]
                results.append((batch_num, original_batch))

    # 按批次顺序合并
    results.sort(key=lambda x: x[0])
    all_enriched = []
    for _, items in results:
        for ep in items:
            if not isinstance(ep, dict):
                continue
            all_enriched.append(ep)

    print(f"  ✅ 富化完成：{len(all_enriched)} 个地点")
    return all_enriched


def step3b_generate_book_meta(
    config: LLMConfig,
    title: str,
    author: str,
    work_type: str,
    era_setting: str,
    places: List[Dict],
) -> Dict:
    """Step 3b: 生成全书元数据（简介、角色表、篇章结构）
    
    这一步解决"新读者无法理解故事"的核心问题：
    - book_summary: 全书简介（封面文案）
    - characters: 角色表（谁是谁）
    - parts: 篇章划分（目录）
    """
    print(f"\n{'='*60}")
    print(f"📖 Step 3b: 生成全书元数据（简介/角色/篇章）")
    print(f"   模型: {MODEL_PRO}")
    print(f"{'='*60}")

    # 构建地点摘要（不传全量数据，节省 token）
    places_summary_parts = []
    for i, p in enumerate(places, 1):
        chars = p.get("narrative_context", {}).get("characters", p.get("characters", []))
        level = p.get("narrative_context", {}).get("event_level", p.get("event_level", "?"))
        part_id = p.get("part_id", "?")
        part_title = p.get("part_title", "?")
        orig_ch = p.get("original_chapter", "?")
        synopsis = p.get("synopsis", p.get("story", ""))
        places_summary_parts.append(
            f"#{i} [{level}] {p.get('title','?')} | part={part_id}({part_title}) | 原著章节={orig_ch} | 人物={chars} | {synopsis[:60]}"
        )
    places_summary = "\n".join(places_summary_parts)

    prompt = BOOK_META_PROMPT.format(
        title=title,
        author=author,
        work_type=work_type,
        era_setting=era_setting,
        places_summary=places_summary,
    )

    try:
        content = call_llm(
            messages=[{"role": "user", "content": prompt}],
            config=config,
            model=MODEL_PRO,
            temperature=0.3,
            expect_json=True,
            max_tokens=4096,
        )
    except Exception as e:
        print(f"  ⚠️  API 调用失败（{e}），返回空元数据")
        return {}

    meta = extract_json_from_text(content)
    if not isinstance(meta, dict):
        print(f"  ⚠️  解析失败，返回空元数据")
        if content:
            print(f"  DEBUG: 返回内容前 200 字: {content[:200]}")
        return {}

    # 打印摘要
    summary = meta.get("book_summary", "")
    chars = meta.get("characters", [])
    parts = meta.get("parts", [])
    print(f"  ✅ 全书简介: {len(summary)} 字")
    print(f"  ✅ 角色表: {len(chars)} 个角色")
    for c in chars:
        imp = c.get("importance", "?")
        name = c.get("name", "?")
        aliases = c.get("aliases", [])
        role = c.get("role", "")
        alias_str = f" (又名: {', '.join(aliases)})" if aliases else ""
        print(f"     [{imp}] {name}{alias_str} — {role[:40]}")
    print(f"  ✅ 篇章结构: {len(parts)} 个篇章")
    for pt in parts:
        print(f"     {pt.get('part_id','?')}: {pt.get('title','?')} ({pt.get('place_count',0)} 地点)")

    return meta


def step4_review(config: LLMConfig, places: List[Dict], title: str = "", author: str = "") -> Tuple[List[Dict], Dict]:
    """Step 4: 质量自审（分批处理，每批 30 个地点）"""
    print(f"\n{'='*60}")
    print(f"🔍 Step 4: 质量自审（{len(places)} 个地点）")
    print(f"   模型: {MODEL_PRO}（纯结构化，无搜索）")
    print(f"{'='*60}")

    REVIEW_BATCH = 16       # 每批地点数
    STEP4_CONCURRENCY = 5   # Step4 并发线程数

    batches = [places[i:i+REVIEW_BATCH] for i in range(0, len(places), REVIEW_BATCH)]
    total_batches = len(batches)

    # ── 单批次审查函数 ──
    def _review_one_batch(args: Tuple[int, List[Dict]]) -> Tuple[int, List[Dict], List[Dict]]:
        """返回 (batch_idx, clean_items, report_items)"""
        batch_idx, batch = args
        prompt = REVIEW_PROMPT.format(
            title=title,
            author=author,
            places_json=json.dumps(batch, ensure_ascii=False, indent=2)
        )
        try:
            content = call_llm(
                messages=[{"role": "user", "content": prompt}],
                config=config,
                model=MODEL_PRO,
                temperature=0.1,
                expect_json=True,
                max_tokens=8192,
            )
        except Exception as e:
            print(f"     ⚠️  审查批次 {batch_idx}/{total_batches} API 失败（{e}），保留原始数据")
            return (batch_idx, batch, [])

        result = extract_json_from_text(content)
        if isinstance(result, dict) and "places" in result:
            result = result["places"]
        if not isinstance(result, list):
            print(f"     ⚠️  审查批次 {batch_idx}/{total_batches} 解析失败，保留原始数据")
            if content:
                print(f"     DEBUG: 返回内容前 200 字: {content[:200]}")
            return (batch_idx, batch, [])

        clean_items = [item for item in result if isinstance(item, dict) and not item.get("_review_report")]
        report_items = [item for item in result if isinstance(item, dict) and item.get("_review_report")]
        print(f"     ✅ 审查批次 {batch_idx}/{total_batches} 通过 {len(clean_items)} 个地点")
        return (batch_idx, clean_items, report_items)

    # ── 并发执行所有审查批次 ──
    print(f"  🚀 并发审查 {total_batches} 个批次（{STEP4_CONCURRENCY} 线程）")
    batch_results: List[Tuple[int, List[Dict], List[Dict]]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=STEP4_CONCURRENCY) as executor:
        futures = {executor.submit(_review_one_batch, (i+1, b)): i for i, b in enumerate(batches)}
        for future in concurrent.futures.as_completed(futures):
            try:
                batch_results.append(future.result())
            except Exception as e:
                idx = futures[future]
                print(f"     ❌ 审查批次 {idx+1} 线程异常: {e}，保留原始数据")
                batch_results.append((idx+1, batches[idx], []))

    # 按批次顺序合并结果
    batch_results.sort(key=lambda x: x[0])
    all_clean: List[Dict] = []
    merged_report: Dict = {}
    for _, clean_items, report_items in batch_results:
        all_clean.extend(clean_items)
        for item in report_items:
            for k in ("fixed_address", "removed_fictional", "removed_not_in_original", "merged_duplicates", "fixed_synopsis"):
                merged_report[k] = merged_report.get(k, 0) + item.get(k, 0)
            if "removed_names" in item:
                merged_report.setdefault("removed_names", []).extend(item["removed_names"])

    if merged_report:
        print(f"  📊 审查汇总报告：")
        print(f"     修复地址: {merged_report.get('fixed_address', 0)}")
        print(f"     移除虚构: {merged_report.get('removed_fictional', 0)}")
        removed_orig = merged_report.get('removed_not_in_original', 0)
        if removed_orig:
            print(f"     移除非原著地点: {removed_orig}")
            removed_names = merged_report.get('removed_names', [])
            if removed_names:
                print(f"     被移除: {', '.join(removed_names)}")
        print(f"     合并重复: {merged_report.get('merged_duplicates', 0)}")
        print(f"     修复synopsis: {merged_report.get('fixed_synopsis', 0)}")
    else:
        print(f"  ✅ 审查完成，{len(all_clean)} 个地点通过")

    return all_clean, merged_report


def step5_output(
    places: List[Dict],
    work_info: Dict,
    output_dir: str,
    report: Dict,
    book_meta: Optional[Dict] = None,
) -> str:
    """Step 5: 最终输出"""
    print(f"\n{'='*60}")
    print(f"💾 Step 5: 输出最终数据")
    print(f"{'='*60}")

    title = work_info.get("title", "unknown")
    author = work_info.get("author", "unknown")
    work_type = work_info.get("type", "novel")

    # pack_id 从 output_dir 的最后一段取得（已经是 book_dir）
    pack_id = os.path.basename(output_dir.rstrip('/'))
    book_dir = output_dir
    os.makedirs(book_dir, exist_ok=True)

    # 分离疑似虚构
    valid_places = [p for p in places if not p.get("fictional_suspect", False)]
    suspects = [p for p in places if p.get("fictional_suspect", False)]

    # 统计
    major = sum(1 for p in valid_places
                if p.get("narrative_context", {}).get("event_level") == "major"
                or p.get("event_level") == "major")
    minor = sum(1 for p in valid_places
                if p.get("narrative_context", {}).get("event_level") == "minor"
                or p.get("event_level") == "minor")
    passing = len(valid_places) - major - minor

    # 地址完整率
    complete_addr = sum(1 for p in valid_places if len(p.get("address", "").split("-")) >= 3)
    addr_completeness = complete_addr / max(len(valid_places), 1)

    # 是否需要 timeline
    timeline_needed = work_type in ("biography", "travelogue", "history")

    # 故事模式统计
    story_mode_places = [p for p in valid_places if p.get("story_mode")]
    story_mode_enabled = len(story_mode_places) > 0
    if story_mode_enabled:
        narrative_lengths = [len(p["story_mode"].get("narrative_text", "")) for p in story_mode_places]
        avg_narrative_len = sum(narrative_lengths) // max(len(narrative_lengths), 1)
        mood_arc = [p["story_mode"].get("mood", "unknown") for p in sorted(
            story_mode_places,
            key=lambda x: x.get("timeline", {}).get("orderIndex", 999)
        )]
        transition_count = sum(1 for p in story_mode_places if p["story_mode"].get("transition_to"))
        transition_coverage = round(transition_count / max(len(story_mode_places) - 1, 1), 2)
    else:
        avg_narrative_len = 0
        mood_arc = []
        transition_coverage = 0.0

    # (A) places_structured.json — 包含全书元数据
    places_file = os.path.join(book_dir, f"{pack_id}_places_structured.json")
    output_data = {
        "book_info": {
            "title": title,
            "author": author,
            "type": work_type,
            "summary": book_meta.get("book_summary", "") if book_meta else "",
        },
        "characters": book_meta.get("characters", []) if book_meta else [],
        "parts": book_meta.get("parts", []) if book_meta else [],
        "places": valid_places,
        "suspects": suspects,
    }
    with open(places_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    # (B) pipeline_meta.json
    meta = {
        "work": {
            "title": title,
            "author": author,
            "type": work_type,
            "locale": "zh-Hans",
        },
        "pipeline": {
            "generated_by": "geolore-auto-pipeline-v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_source_mode": "full_text",
            "data_source_warning": None,
            "model_select": MODEL_PRO,
            "model_extract": MODEL_PRO,
            "total_places": len(valid_places),
            "major_places": major,
            "minor_places": minor,
            "passing_places": passing,
            "fictional_suspects": len(suspects),
            "address_completeness": round(addr_completeness, 2),
            "timeline_enabled": timeline_needed,
            "story_mode_enabled": story_mode_enabled,
            "story_mode_stats": {
                "total_chapters": len(story_mode_places),
                "avg_narrative_length": avg_narrative_len,
                "mood_arc": mood_arc,
                "transition_coverage": transition_coverage,
            } if story_mode_enabled else None,
            "suggested_pack_id": pack_id,
            "suggested_map_title": f"《{title}》巡礼地图",
        },
        "review": report,
        "next_steps": [
            f"python scripts/geocode_places.py --input {places_file} --output {book_dir}/{pack_id}_geocoded.json --amap-key $AMAP_KEY --enable-validation",
            f"python scripts/build_pack.py --input {book_dir}/{pack_id}_geocoded.json --output {book_dir}/{pack_id}_pack.json --pack-id {pack_id} --title \"《{title}》巡礼地图\"",
        ],
    }
    meta_file = os.path.join(book_dir, f"{pack_id}_pipeline_meta.json")
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"  📁 输出目录: {book_dir}/")
    print(f"  📄 {pack_id}_places_structured.json ({len(valid_places)} 个地点)")
    print(f"  📄 {pack_id}_pipeline_meta.json")
    print(f"\n  📊 汇总：")
    print(f"     有效地点: {len(valid_places)} | 疑似虚构: {len(suspects)}")
    print(f"     major: {major} | minor: {minor} | passing: {passing}")
    print(f"     地址完整率: {addr_completeness:.0%}")
    return places_file


# ─────────────────────────── Main Pipeline ────────────────────


def _checkpoint_path(book_dir: str, step: str) -> str:
    """返回某步骤的 checkpoint 文件路径"""
    return os.path.join(book_dir, f"_checkpoint_{step}.json")


def _save_checkpoint(book_dir: str, step: str, data: Any) -> None:
    """保存某步骤的中间结果到 checkpoint 文件"""
    path = _checkpoint_path(book_dir, step)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  💾 [checkpoint] {step} → {os.path.basename(path)}")


def _load_checkpoint(book_dir: str, step: str) -> Optional[Any]:
    """加载某步骤的 checkpoint，不存在则返回 None"""
    path = _checkpoint_path(book_dir, step)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"  ♻️  [checkpoint] 恢复 {step} ← {os.path.basename(path)}")
        return data
    return None


def _clear_checkpoints(book_dir: str) -> None:
    """pipeline 完成后删除所有 checkpoint 文件"""
    for step in ("step2", "step3", "step3b", "step4"):
        path = _checkpoint_path(book_dir, step)
        if os.path.exists(path):
            os.remove(path)
    print(f"  🧹 已清除所有 checkpoint 文件")


def run_pipeline_for_work(
    config: LLMConfig,
    title: str,
    author: str,
    work_type: str = "novel",
    era_setting: str = "",
    geo_scope: str = "",
    output_dir: str = "output",
    min_places: int = 15,
    tracker: Optional[Any] = None,
    text_file: Optional[str] = None,
    resume_from: Optional[str] = None,
) -> Optional[str]:
    """对一部作品执行完整流水线

    数据来源优先级：
    1. --text-file 手动提供的原文文件
    2. Step 0b 自动获取（Gutenberg/Wikisource/Open Library）
    3. 无原文 → 终止（不使用 LLM 搜索，避免幻觉）

    断点续跑：
    - 每步完成后自动保存 _checkpoint_{step}.json
    - resume_from 可指定从哪步继续：step2 / step3 / step3b / step4
    - 默认自动检测已有 checkpoint 并跳过对应步骤
    - pipeline 全部完成后自动清除 checkpoint 文件
    """
    print(f"\n{'#'*60}")
    print(f"# 🚀 开始处理：《{title}》— {author}")
    print(f"{'#'*60}")

    start_time = time.time()

    # 追踪：注册书籍
    if tracker:
        tracker.add_book(title, author, book_type=work_type, era_setting=era_setting,
                         geo_scope=geo_scope, status="processing")
        tracker.update_book(title, started_at=tracker._now())

    # Step 0b: 获取原文（唯一数据来源）
    work_text = None

    # 优先级 1: 手动提供的原文文件
    if text_file:
        print(f"\n{'='*60}")
        print(f"📄 Step 0b: 加载手动提供的原文")
        print(f"   文件: {text_file}")
        print(f"{'='*60}")
        if not os.path.isfile(text_file):
            print(f"  ❌ 文件不存在: {text_file}")
            if tracker:
                tracker.update_book(title, status="failed", error_message=f"原文文件不存在: {text_file}")
            return None
        try:
            with open(text_file, "r", encoding="utf-8") as f:
                manual_text = f.read()
            if len(manual_text.strip()) < 500:
                print(f"  ❌ 文件内容过短（{len(manual_text)} 字符），请提供完整原文")
                if tracker:
                    tracker.update_book(title, status="failed", error_message="原文文件内容过短")
                return None
            # 保留完整全文，分块逻辑由 step2_extract_places 负责
            work_text = (
                f"═══ 原文数据（来源: 手动提供）═══\n"
                f"作品: 《{title}》\n"
                f"作者: {author}\n"
                f"文件: {text_file}\n"
                f"字数: {len(manual_text):,}\n"
                f"═══════════════════════════════════════\n\n"
                + manual_text
            )
            print(f"  ✅ 已加载完整原文: {len(manual_text):,} 字符（Step 2 将分块处理）")
            if tracker:
                sid = tracker.start_step(title, "step0b_load_text_file")
                tracker.finish_step(sid, "completed", output_size=len(manual_text),
                                    notes=f"手动提供原文: {text_file}")
        except Exception as e:
            print(f"  ❌ 读取文件失败: {e}")
            if tracker:
                tracker.update_book(title, status="failed", error_message=f"读取原文失败: {e}")
            return None

    # 优先级 2: 自动从开放数据库获取
    if not work_text:
        if tracker:
            sid = tracker.start_step(title, "step0b_fetch_text")
        fetched_text = step0b_fetch_text(title, author)
        if tracker:
            if fetched_text:
                tracker.finish_step(sid, "completed", output_size=len(fetched_text),
                                    notes="原文获取成功")
            else:
                tracker.finish_step(sid, "failed", notes="未获取到原文")
        work_text = fetched_text

    # 无原文 → 终止（不 fallback 到 LLM 搜索）
    if not work_text or len(work_text.strip()) < 500:
        print(f"\n  ❌ 未获取到《{title}》的原文")
        print(f"  ℹ️  本流水线要求必须有原文才能提取地点，避免 LLM 幻觉。")
        print(f"  💡 解决方案：")
        print(f"     1. 手动准备原文文件（.txt），然后使用 --text-file 参数:")
        print(f"        python scripts/auto_pipeline.py --mode specify --work \"{title}\" --author \"{author}\" --text-file /path/to/{title}.txt")
        print(f"     2. 将原文文件放到缓存目录 output/.text_cache/ 中（或用 --text-file 指定路径）")
        print(f"     3. 对于版权保护的作品，请从合法渠道获取电子版后提供")
        if tracker:
            tracker.update_book(title, status="failed",
                                error_message="未获取到原文，请通过 --text-file 手动提供")
        return None

    # 保存原文到工作目录（pack_id 子目录）
    # 允许中文、字母、数字；其他字符替换为连字符
    pack_id = re.sub(r'[^\w\u4e00-\u9fff]+', '-', title).strip('-')
    if not pack_id:
        pack_id = f"work-{int(time.time())}"
    book_dir = os.path.join(output_dir, pack_id)
    os.makedirs(book_dir, exist_ok=True)
    source_file = os.path.join(book_dir, f"source_{title}.md")
    with open(source_file, "w", encoding="utf-8") as f:
        f.write(f"# 《{title}》— {author}\n\n{work_text}")

    # ── 断点续跑辅助：判断某步是否需要跳过 ──
    # resume_from=None 时：自动检测 checkpoint 文件决定是否跳过
    # resume_from="step3" 时：强制从 step3 重跑（丢弃 step3/3b/4 的旧 checkpoint）
    _STEP_ORDER = ["step2", "step3", "step3b", "step4"]
    if resume_from and resume_from in _STEP_ORDER:
        # 清除 resume_from 及之后步骤的旧 checkpoint，强制重跑
        idx = _STEP_ORDER.index(resume_from)
        for s in _STEP_ORDER[idx:]:
            p = _checkpoint_path(book_dir, s)
            if os.path.exists(p):
                os.remove(p)
                print(f"  🗑️  清除旧 checkpoint: {os.path.basename(p)}")
        print(f"  ▶️  将从 {resume_from} 开始重跑（之前步骤若有 checkpoint 则复用）")

    # ── Step 2: 提取地点 ──────────────────────────────────────
    ckpt2 = _load_checkpoint(book_dir, "step2")
    if ckpt2 is not None:
        raw_places = ckpt2
        print(f"  ⏩ Step 2 已跳过（checkpoint 中有 {len(raw_places)} 个地点）")
    else:
        if tracker:
            sid2 = tracker.start_step(title, "step2_extract_places")
        raw_places = step2_extract_places(
            config, title, author, work_type, era_setting, geo_scope,
            work_text, min_places=min_places,
        )
        if tracker:
            tracker.finish_step(
                sid2, "completed" if raw_places else "failed",
                output_size=len(raw_places) if raw_places else 0,
                notes=f"提取到 {len(raw_places)} 个地点" if raw_places else "提取失败",
            )
        if not raw_places:
            print(f"  ❌ 未能提取到地点")
            if tracker:
                tracker.update_book(title, status="failed", error_message="地点提取失败")
            return None
        _save_checkpoint(book_dir, "step2", raw_places)

    # 保存 Step 2 的 source_evidence，以便 Step 3 之后恢复
    evidence_map = {}
    for p in raw_places:
        key = p.get("title", "")
        if key:
            evidence_map[key] = {
                "source_evidence": p.get("source_evidence"),
            }

    # ── Step 3: 结构化富化 ────────────────────────────────────
    ckpt3 = _load_checkpoint(book_dir, "step3")
    if ckpt3 is not None:
        enriched = ckpt3
        print(f"  ⏩ Step 3 已跳过（checkpoint 中有 {len(enriched)} 个富化地点）")
    else:
        if tracker:
            sid3 = tracker.start_step(title, "step3_enrich_places")
        enriched = step3_enrich_places(
            config, title, author, work_type, era_setting, raw_places
        )
        if tracker:
            tracker.finish_step(
                sid3, "completed",
                output_size=len(enriched) if enriched else 0,
                notes=f"富化完成 {len(enriched)} 条" if enriched else "富化无结果",
            )
        # Step 3 后处理：恢复 source_evidence（Step 3 可能覆盖或丢失原文引证）
        restored = 0
        for p in enriched:
            key = p.get("title", "")
            if key in evidence_map:
                saved = evidence_map[key]
                if not p.get("source_evidence") and saved.get("source_evidence"):
                    p["source_evidence"] = saved["source_evidence"]
                    restored += 1
        if restored:
            print(f"  🔄 从 Step 2 恢复了 {restored} 个地点的 source_evidence")
        _save_checkpoint(book_dir, "step3", enriched)

    # ── Step 3b: 生成全书元数据 ───────────────────────────────
    ckpt3b = _load_checkpoint(book_dir, "step3b")
    if ckpt3b is not None:
        book_meta = ckpt3b
        print(f"  ⏩ Step 3b 已跳过（checkpoint 中有全书元数据）")
    else:
        book_meta = {}
        if tracker:
            sid3b = tracker.start_step(title, "step3b_book_meta")
        try:
            book_meta = step3b_generate_book_meta(
                config, title, author, work_type, era_setting, enriched
            )
        except Exception as e:
            print(f"  ⚠️  Step 3b 失败（{e}），继续不含全书元数据")
        if tracker:
            tracker.finish_step(
                sid3b, "completed" if book_meta else "failed",
                notes=f"元数据: {len(book_meta.get('characters',[]))} 角色, {len(book_meta.get('parts',[]))} 篇章" if book_meta else "元数据生成失败",
            )
        _save_checkpoint(book_dir, "step3b", book_meta)

    # ── Step 4: 质量审查 ──────────────────────────────────────
    ckpt4 = _load_checkpoint(book_dir, "step4")
    if ckpt4 is not None:
        reviewed = ckpt4.get("places", [])
        report = ckpt4.get("report", {})
        print(f"  ⏩ Step 4 已跳过（checkpoint 中有 {len(reviewed)} 个审查后地点）")
    else:
        if tracker:
            sid4 = tracker.start_step(title, "step4_review")
        reviewed, report = step4_review(config, enriched, title=title, author=author)
        if tracker:
            tracker.finish_step(
                sid4, "completed",
                output_size=len(reviewed) if reviewed else 0,
                notes=f"审查完成 {len(reviewed)} 条" if reviewed else "审查无结果",
            )
        _save_checkpoint(book_dir, "step4", {"places": reviewed, "report": report})

    # Step 5: 输出（传入 book_dir，由 step5_output 直接使用）
    if tracker:
        sid5 = tracker.start_step(title, "step5_output")
    work_meta = {"title": title, "author": author, "type": work_type}
    result_file = step5_output(reviewed, work_meta, book_dir, report, book_meta=book_meta)
    if tracker:
        tracker.finish_step(
            sid5, "completed",
            notes=f"输出文件: {result_file}" if result_file else "输出失败",
        )

    # 全部步骤成功完成，清除 checkpoint 文件（保持目录整洁）
    if result_file:
        _clear_checkpoints(book_dir)

    # 更新 registry 状态为 completed
    if HAS_REGISTRY:
        try:
            reg = load_registry(DEFAULT_REGISTRY_PATH)
            found = False
            for b in reg.get("books", []):
                if b.get("title") == title:
                    b["status"] = "completed"
                    b["output_file"] = result_file
                    found = True
                    break
            if not found:
                # 如果不在 registry 中（如手动指定的作品），添加之
                add_book(
                    reg, title=title, author=author, book_type=work_type,
                    era_setting=era_setting, geo_scope=geo_scope,
                    status="completed",
                    extra={"output_file": result_file},
                )
            save_registry(reg, DEFAULT_REGISTRY_PATH)
        except Exception as e:
            print(f"  ⚠️  更新注册表失败: {e}")

    elapsed = time.time() - start_time
    print(f"\n  ⏱️  总耗时: {elapsed:.1f}s")

    # 追踪：标记完成
    if tracker:
        place_count = len(reviewed) if reviewed else 0
        tracker.update_book(
            title, status="completed",
            output_file=result_file,
            places_final=place_count,
            elapsed_sec=elapsed,
            finished_at=tracker._now(),
        )

    return result_file


def main():
    parser = argparse.ArgumentParser(
        description="故实巡礼 · AI 全自动内容生产流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # AI 自主选题（模式 D）
  python scripts/auto_pipeline.py --mode select --count 5

  # 指定作品
  python scripts/auto_pipeline.py --mode specify --work "繁花" --author "金宇澄"

  # 只执行选题（不生产内容）
  python scripts/auto_pipeline.py --mode select --count 10 --select-only
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["select", "specify", "resume"],
        required=True,
        help="select=AI选题, specify=指定作品, resume=从选题文件继续",
    )
    parser.add_argument("--count", type=int, default=5, help="选题数量（mode=select）")
    parser.add_argument("--work", help="作品名称（mode=specify）")
    parser.add_argument("--author", help="作者（mode=specify）")
    parser.add_argument("--work-type", default="novel", help="作品类型")
    parser.add_argument("--era", default="", help="时代背景")
    parser.add_argument("--geo-scope", default="", help="地理范围")
    parser.add_argument("--text-file", help="手动提供原文文件路径（.txt/.md），用于无法自动获取原文的作品")
    parser.add_argument("--topics-file", help="选题文件路径（mode=resume）")
    parser.add_argument("--select-only", action="store_true", help="只选题不生产")
    parser.add_argument("--min-places", type=int, default=15, help="最少提取地点数")
    parser.add_argument(
        "--resume-from",
        choices=["step2", "step3", "step3b", "step4"],
        default=None,
        help="断点续跑：从指定步骤开始重跑（step2/step3/step3b/step4）。\n"
             "不指定时自动检测 checkpoint 文件决定跳过哪些步骤。",
    )
    parser.add_argument("--output", default="output/books", help="每本书产出目录")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("GEOLORE_API_KEY", ""),
        help="API Key (或设置 GEOLORE_API_KEY 环境变量)",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("GEOLORE_BASE_URL", DEFAULT_BASE_URL),
        help="API Base URL",
    )
    parser.add_argument(
        "--registry",
        default=DEFAULT_REGISTRY_PATH,
        help="书籍注册表路径（记忆系统）",
    )
    parser.add_argument(
        "--tracking-dir",
        default="output",
        dest="tracking_dir",
        help="CSV 追踪文件存放目录",
    )
    parser.add_argument(
        "--export-csv",
        action="store_true",
        help="运行结束后导出 CSV 报告",
    )
    args = parser.parse_args()

    if not args.api_key:
        # 尝试从 .ai_config.json 和环境变量加载
        fallback_config = load_llm_config()
        args.api_key = fallback_config.api_key
        if not args.base_url or args.base_url == DEFAULT_BASE_URL:
            args.base_url = fallback_config.base_url

    if not args.api_key:
        print("❌ 需要 API Key: --api-key 或环境变量 GEOLORE_API_KEY 或 .ai_config.json")
        sys.exit(1)

    config = LLMConfig(api_key=args.api_key, base_url=args.base_url)

    # 初始化追踪器
    tracker = None
    if HAS_TRACKER:
        tracker = PipelineTracker(args.tracking_dir)
        tracker.start_run(mode=args.mode, config={
            "api_key": "***",
            "base_url": args.base_url,
            "mode": args.mode,
            "count": getattr(args, 'count', 0),
            "work": getattr(args, 'work', ''),
        })

    # ── Mode: specify ──
    if args.mode == "specify":
        if not args.work:
            print("❌ mode=specify 需要 --work 参数")
            sys.exit(1)
        run_pipeline_for_work(
            config,
            title=args.work,
            author=args.author or "未知",
            work_type=args.work_type,
            era_setting=args.era,
            geo_scope=args.geo_scope,
            output_dir=args.output,
            min_places=args.min_places,
            tracker=tracker,
            text_file=getattr(args, 'text_file', None),
            resume_from=getattr(args, 'resume_from', None),
        )
        # 追踪：结束运行 & 导出
        if tracker:
            tracker.finish_run("completed")
            tracker.print_dashboard()
            if args.export_csv:
                tracker.export_all_csv(args.output)
        return

    # ── Mode: select / resume ──
    topics = []

    if args.mode == "select":
        topics = step0_select_topics(config, args.count, registry_path=args.registry)
        if not topics:
            print("❌ 选题失败")
            sys.exit(1)

        # 保存选题
        os.makedirs(args.output, exist_ok=True)
        topics_file = os.path.join(args.output, "topics.json")
        with open(topics_file, "w", encoding="utf-8") as f:
            json.dump(topics, f, ensure_ascii=False, indent=2)
        print(f"\n💾 选题已保存: {topics_file}")

        if args.select_only:
            print("\n✅ 选题完成（--select-only 模式，不执行生产）")
            return

    elif args.mode == "resume":
        if not args.topics_file:
            print("❌ mode=resume 需要 --topics-file 参数")
            sys.exit(1)
        with open(args.topics_file, "r", encoding="utf-8") as f:
            topics = json.load(f)
        print(f"📂 加载 {len(topics)} 个选题: {args.topics_file}")

    # 对 S/A 级作品执行流水线
    results = []
    for topic in topics:
        grade = topic.get("grade", "C")
        if grade not in ("S", "A"):
            print(f"\n⏭️  跳过 [{grade}级] 《{topic.get('title')}》")
            continue

        result = run_pipeline_for_work(
            config,
            title=topic.get("title", ""),
            author=topic.get("author", ""),
            work_type=topic.get("type", "novel"),
            era_setting=topic.get("era_setting", ""),
            geo_scope=topic.get("geo_scope", ""),
            output_dir=args.output,
            min_places=args.min_places,
            tracker=tracker,
        )
        if result:
            results.append(result)

        # 作品间间隔
        time.sleep(2)

    # 汇总
    print(f"\n{'='*60}")
    print(f"🎉 全部完成！")
    print(f"   处理作品: {len(results)} 部")
    for r in results:
        print(f"   📄 {r}")
    print(f"\n下一步：对每个 *_places_structured.json 执行地理编码")
    print(f"   python scripts/geocode_places.py --input <file> --output <out> --amap-key $AMAP_KEY --enable-validation")
    print(f"{'='*60}")

    # 追踪：结束运行 & 导出
    if tracker:
        tracker.finish_run("completed")
        tracker.print_dashboard()
        if args.export_csv:
            tracker.export_all_csv(args.output)


if __name__ == "__main__":
    main()
