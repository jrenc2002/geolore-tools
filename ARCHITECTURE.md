# 🏗️ Geolore Tools 架构整理

> 最后更新：2026-03-02  
> 本文档完整梳理 `geolore_tools` 的文件结构、数据流、数据库设计与执行流程。

---

## 📋 目录

1. [项目定位](#1-项目定位)
2. [文件架构总览](#2-文件架构总览)
3. [核心模块详解 (src/)](#3-核心模块详解)
4. [脚本层详解 (scripts/)](#4-脚本层详解)
5. [数据库设计 (SQLite)](#5-数据库设计)
6. [数据格式与文件规范](#6-数据格式与文件规范)
7. [完整流水线流程图](#7-完整流水线流程图)
8. [两条工作流对比](#8-两条工作流对比)
9. [配置与环境变量](#9-配置与环境变量)
10. [当前问题与改进建议](#10-当前问题与改进建议)

---

## 1. 项目定位

**Geolore Tools** 是「故实巡礼」iOS 应用的 **内容数据生产线**。

核心使命：**文学作品 → 真实地理坐标 → 可巡礼的地图内容包**

```
输入: 一部文学作品（书名/原文）
输出: ContentPack JSON → 导入 iOS 应用 → 用户在现实世界巡礼
```

---

## 2. 文件架构总览

```
geolore_tools/
│
├── src/                          # 🧠 核心模块层（可复用的 Python 库）
│   ├── __init__.py
│   ├── common/                   # ⓪ 公共基础设施（2025-03 新增）
│   │   ├── __init__.py           #    统一导出
│   │   ├── config.py             #    LLMConfig / GeocodingConfig / 模型常量
│   │   ├── llm_client.py         #    统一 LLM HTTP 调用（WAF 规避、代理、重试）
│   │   └── json_utils.py         #    从 LLM 脏输出中提取 JSON
│   ├── textsource/               # ① 原文获取
│   │   ├── __init__.py
│   │   └── fetcher.py            #    Gutenberg/Wikisource/OpenLibrary/IA/SE 多源抓取
│   ├── extraction/               # ② 文本处理 & LLM 抽取
│   │   ├── __init__.py
│   │   ├── splitter.py           #    按章节分片
│   │   ├── prompt_generator.py   #    生成 JSONL 格式提示词
│   │   └── llm_runner.py         #    JSONL 批量抽取（委托 common.llm_client）
│   ├── processing/               # ③ 数据后处理
│   │   ├── __init__.py
│   │   ├── merger.py             #    按 title 合并同名地点
│   │   ├── cleaner.py            #    LLM 异步批量清洗 synopsis（使用 common.json_utils）
│   │   └── filter.py             #    过滤无效/过宽地址
│   ├── geocoding/                # ④ 地理编码
│   │   ├── __init__.py
│   │   ├── nominatim.py          #    OSM Nominatim 免费编码
│   │   ├── amap.py               #    高德地图 API 编码（中国地点精准）
│   │   └── validator.py          #    行政区一致性 + 距离合理性校验
│   ├── packing/                  # ⑤ 内容包构建
│   │   ├── __init__.py
│   │   └── pack_builder.py       #    生成 ContentPack v2 JSON
│   ├── memory/                   # ⑥ 记忆系统
│   │   ├── __init__.py
│   │   └── book_registry.py      #    书籍注册表（防重复选题）
│   └── tracking/                 # ⑦ 流水线追踪
│       ├── __init__.py
│       └── tracker.py            #    SQLite 全生命周期日志
│
├── scripts/                      # 🎛️ 命令行脚本层（可独立运行）
│   ├── auto_pipeline.py          #    ⭐ 全自动一体化流水线入口
│   ├── recommend_books.py        #    AI 选书推荐（带记忆）
│   ├── fetch_text.py             #    原文获取 CLI
│   ├── split_chapters.py         #    文本分片 CLI
│   ├── generate_prompts.py       #    提示词生成 CLI
│   ├── run_extraction.py         #    LLM 抽取 CLI
│   ├── process_data.py           #    数据处理流水线 CLI (Merge→Clean→Filter)
│   ├── geocode_places.py         #    地理编码 CLI
│   ├── build_pack.py             #    内容包构建 CLI
│   ├── fix_geocode_template.py   #    编码修复模板（高德回退策略）
│   └── test_fetch_and_track.py   #    原文获取 + 追踪系统集成测试
│
├── prompts/                      # 📝 LLM 提示词模板
│   ├── README.md
│   ├── extraction.md             #    地点抽取提示词
│   ├── cleaning.md               #    synopsis 清洗提示词
│   ├── book_recommendation.md    #    选书推荐提示词
│   └── meta_sop_generator.md     #    SOP 生成提示词
│
├── docs/                         # 📚 文档
│   ├── SOP.md                    #    标准操作流程（手动分步）
│   ├── ContentPackSpec.md        #    ContentPack v2 JSON 协议规范
│   ├── CloudKitSchema.json       #    iOS 端 CloudKit 数据模型
│   ├── GeocodingRules.md         #    地理编码规则
│   ├── SelectionCriteria.md      #    选题标准
│   ├── TimelineSpec.md           #    时间线规范
│   ├── ValidationMechanism.md    #    验证机制
│   └── TroubleshootingGuide.md   #    故障排除
│
├── output/                       # 📦 运行产物（gitignore 推荐）
│   ├── .text_cache/              #    原文本地缓存（md5 命名）
│   ├── registry.json             #    书籍注册表（记忆系统）
│   ├── pipeline_tracker.db       #    SQLite 追踪数据库
│   ├── topics.json               #    AI 选题结果
│   ├── books_report.csv          #    书目追踪 CSV
│   ├── text_fetches_report.csv   #    原文获取日志 CSV
│   ├── fulltext/                 #    下载的原文存放
│   ├── *_places_structured.json  #    各作品的结构化地点（最终产物）
│   └── *_pipeline_meta.json      #    各作品的流水线元数据
│
├── cases/                        # 📂 案例数据
│   ├── fanhua-novel/             #    繁花
│   └── beipai-novel/             #    北派盗墓笔记
│
├── examples/                     # 📂 示例模板
│   ├── novel/                    #    小说类
│   └── biography/                #    传记类
│
├── requirements.txt              # 依赖声明
├── .env                          # 环境变量（API Key 等）
├── .gitignore
└── README.md                     # 项目说明
```

---

## 3. 核心模块详解

### 模块依赖关系

```
memory/book_registry ─────────────────────────────────────┐
                                                          │
textsource/fetcher ──→ extraction/splitter ──→ extraction/prompt_generator ──→ extraction/llm_runner
                                                          │
                               processing/merger ──→ processing/cleaner ──→ processing/filter
                                                          │
                               geocoding/nominatim ──→ geocoding/validator
                               geocoding/amap      ──→ geocoding/validator
                                                          │
                                             packing/pack_builder ──→ ContentPack JSON
                                                          │
tracking/tracker ─────────────────────────── (贯穿全流程) ─┘
```

### 各模块职责

| 模块 | 文件 | 职责 | 输入 | 输出 |
|------|------|------|------|------|
| **textsource** | `fetcher.py` | 从6个开放文学数据源获取全文 | 书名+作者 | `TextResult` (全文/摘要) |
| **extraction** | `splitter.py` | 按章节标题分片 | `.txt` 文件 | `chunk_*.txt` + `index.json` |
| **extraction** | `prompt_generator.py` | 为分片生成 JSONL 提示词 | chunks 目录 | `prompts.jsonl` |
| **extraction** | `llm_runner.py` | 调用 LLM 批量抽取 | JSONL 提示词 | 抽取结果 JSON |
| **processing** | `merger.py` | 按 title 合并同名地点 | JSONL 抽取结果 | 去重 JSON 数组 |
| **processing** | `cleaner.py` | LLM 批量凝练 synopsis | JSON 数组 | 清洗后 JSON |
| **processing** | `filter.py` | 过滤省级/无效地址 | JSON 数组 | 过滤后 JSON |
| **geocoding** | `nominatim.py` | OSM 免费地理编码 | 地名列表 | `{lat, lon, ...}` |
| **geocoding** | `amap.py` | 高德 API 编码（中国精准） | 地名列表 | `{lat, lon, ...}` |
| **geocoding** | `validator.py` | 编码结果校验 | 地址层级+编码结果 | 通过/失败+原因 |
| **packing** | `pack_builder.py` | 构建 ContentPack v2 | 编码后的地点 | ContentPack JSON |
| **memory** | `book_registry.py` | 书籍注册表，防重复推荐 | `registry.json` | 记忆块文本 |
| **tracking** | `tracker.py` | SQLite 全流程追踪 | 流水线事件 | DB + CSV |

---

## 4. 脚本层详解

### 核心入口脚本

| 脚本 | 用途 | 调用的模块 |
|------|------|-----------|
| `auto_pipeline.py` | ⭐ **全自动一体化流水线** | memory + textsource + extraction + tracking |
| `recommend_books.py` | AI 选书推荐（独立于 pipeline） | memory |

### 分步工具脚本

| 脚本 | 流水线阶段 | 调用的模块 |
|------|-----------|-----------|
| `fetch_text.py` | 原文获取 | textsource |
| `split_chapters.py` | 文本分片 | extraction.splitter |
| `generate_prompts.py` | 提示词生成 | extraction.prompt_generator |
| `run_extraction.py` | LLM 抽取 | extraction.llm_runner |
| `process_data.py` | 合并→清洗→过滤 | processing.* |
| `geocode_places.py` | 地理编码 | geocoding.* |
| `build_pack.py` | 内容包构建 | packing |
| `fix_geocode_template.py` | 编码修复模板 | geocoding.amap |

### 测试脚本

| 脚本 | 用途 |
|------|------|
| `test_fetch_and_track.py` | 原文获取 + 追踪系统集成测试 |

---

## 5. 数据库设计

### SQLite 追踪数据库 (`pipeline_tracker.db`)

```
┌─────────────────────────────────────────────────────┐
│  pipeline_runs  (每次运行一条)                        │
│─────────────────────────────────────────────────────│
│  PK  run_id         TEXT    "run_{timestamp}_{pid}" │
│      mode           TEXT    select/specify/resume    │
│      started_at     TEXT    UTC datetime             │
│      finished_at    TEXT                             │
│      status         TEXT    running/completed/failed │
│      total_books    INT                              │
│      books_succeeded INT                             │
│      books_failed   INT                              │
│      config_json    TEXT    运行参数快照              │
└─────────────────────────────────────────────────────┘
         │ 1:N
         ▼
┌─────────────────────────────────────────────────────┐
│  books  (每本书一条)                                  │
│─────────────────────────────────────────────────────│
│  PK  id             INTEGER AUTOINCREMENT           │
│  FK  run_id         TEXT                             │
│      title          TEXT    书名                     │
│      title_en       TEXT    英文名                   │
│      author         TEXT                             │
│      language       TEXT    zh/en/fr/...             │
│      book_type      TEXT    novel/travelogue/...     │
│      grade          TEXT    S/A/B                    │
│      geo_region     TEXT    地理区域标签              │
│      geo_scope      TEXT    地理范围描述              │
│      era_setting    TEXT    时代背景                  │
│      place_count_est INT   AI 预估地点数             │
│      density_index  REAL   地点密度指数              │
│      reachability   INT    现实可达率 %              │
│      reason         TEXT   选题理由                   │
│      status         TEXT   recommended→fetching→     │
│                            extracting→completed/failed│
│      text_source    TEXT   gutenberg/wikisource/...  │
│      text_fetched   INT   0/1                        │
│      text_is_full   INT   0/1                        │
│      text_word_count INT  字数                       │
│      text_url       TEXT                             │
│      places_extracted INT 提取地点数                  │
│      places_final   INT   最终地点数                  │
│      output_file    TEXT  输出文件路径                │
│      error_message  TEXT                             │
│      elapsed_sec    REAL  处理耗时(秒)               │
│      created_at     TEXT                             │
└─────────────────────────────────────────────────────┘
         │ 1:N
         ▼
┌─────────────────────────────────────────────────────┐
│  text_fetches  (每次获取尝试一条)                     │
│─────────────────────────────────────────────────────│
│  PK  id             INTEGER AUTOINCREMENT           │
│  FK  run_id         TEXT                             │
│      book_title     TEXT                             │
│      source         TEXT    gutenberg/wikisource/... │
│      searched_at    TEXT                             │
│      found          INT    0/1                       │
│      is_full_text   INT    0/1                       │
│      word_count     INT                              │
│      url            TEXT                             │
│      error          TEXT                             │
│      response_ms    INT    响应耗时(ms)              │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  pipeline_steps  (每个步骤一条)                       │
│─────────────────────────────────────────────────────│
│  PK  id             INTEGER AUTOINCREMENT           │
│  FK  run_id         TEXT                             │
│      book_title     TEXT                             │
│      step_name      TEXT    step0_select/step0b_fetch│
│                            /step2_extract/step3_enrich│
│                            /step4_review/step5_output│
│      started_at     TEXT                             │
│      finished_at    TEXT                             │
│      status         TEXT    running/completed/failed │
│      model_used     TEXT    使用的 LLM 模型          │
│      input_size     INT    输入字符数                │
│      output_size    INT    输出字符数                │
│      item_count     INT    处理项数                  │
│      notes          TEXT                             │
│      error          TEXT                             │
└─────────────────────────────────────────────────────┘
```

**索引**：
- `idx_books_run` → `books(run_id)`
- `idx_books_status` → `books(status)`
- `idx_text_fetches_run` → `text_fetches(run_id)`
- `idx_steps_run` → `pipeline_steps(run_id)`

### JSON 注册表 (`registry.json`)

```json
{
  "schema_version": 1,
  "books": [
    {
      "title": "书名",
      "title_en": "英文名",
      "aliases": [],
      "author": "作者",
      "language": "zh",
      "type": "novel",
      "grade": "S",
      "geo_region": "区域",
      "status": "recommended|processing|completed|skipped",
      "added_at": "ISO 8601",
      "output_file": "路径"
    }
  ],
  "stats": {
    "total_books": 1,
    "by_language": {},
    "by_type": {},
    "by_region": {},
    "by_grade": {}
  }
}
```

---

## 6. 数据格式与文件规范

### 流水线中间数据格式

```
┌──────────────────┐    ┌──────────────────────┐    ┌───────────────────────────────┐
│  原文 (.txt)      │ →  │  分片 chunk_*.txt     │ →  │  JSONL 提示词                  │
│  UTF-8 纯文本     │    │  + index.json        │    │  {"chunkFile","input":{       │
│                  │    │                      │    │   "instructions","schema",    │
│                  │    │                      │    │   "text"}}                    │
└──────────────────┘    └──────────────────────┘    └───────────────────────────────┘
                                                                │
                                                                ▼
┌──────────────────────────────────────────┐    ┌──────────────────────────────────┐
│  地点抽取结果 (JSON 数组)                  │ ←  │  LLM 输出                        │
│  [{                                      │    │                                │
│    "title": "地点名",                     │    └──────────────────────────────────┘
│    "address": "国家-城市-具体地点",        │
│    "story": "≤100字情节",                 │
│    "source_evidence": "原文引用",          │
│    "event_level": "major|minor|passing",  │
│    "characters": ["人物"],                │
│    "fictional_suspect": false             │
│  }]                                      │
└──────────────────────────────────────────┘
         │
         ▼ (合并去重 + 结构化富化 + 质量审查)
┌──────────────────────────────────────────────────────────────┐
│  *_places_structured.json  (最终产物)                          │
│  {                                                           │
│    "places": [{                                              │
│      "title", "address", "synopsis", "source_evidence",      │
│      "temporal_context": { "era", "historical_name", ... },  │
│      "narrative_context": { "event_level", "characters" },   │
│      "cultural_tags": { "category", "themes", "significance"}│
│      "timeline": { "orderIndex", "dateStart", "dateEnd" },   │
│      "story_mode": {                                         │
│        "chapter_title", "hook", "narrative_text",            │
│        "transition_to", "mood", "key_dialogue"               │
│      }                                                       │
│    }],                                                       │
│    "suspects": [...]                                         │
│  }                                                           │
└──────────────────────────────────────────────────────────────┘
         │
         ▼ (地理编码)
┌──────────────────────────────────────────┐
│  *_geocoded.json                         │
│  [{ ...原有字段,                          │
│     "latitude", "longitude",             │
│     "locality", "countryCode",           │
│     "clientId", "geocodeSuccess"         │
│  }]                                      │
└──────────────────────────────────────────┘
         │
         ▼ (打包)
┌──────────────────────────────────────────┐
│  ContentPack v2 JSON → iOS 应用导入       │
│  { "schemaVersion": 2,                   │
│    "pack": {id, version, title},         │
│    "map": {title, defaultLat/Lon/Zoom},  │
│    "places": [{clientId, title,          │
│       lat, lon, synopsis, timeline,      │
│       storyMode}],                       │
│    "mapPlaces": [{placeClientId,         │
│       orderIndex}]                       │
│  }                                       │
└──────────────────────────────────────────┘
```

---

## 7. 完整流水线流程图

### 🤖 全自动模式 (`auto_pipeline.py`)

```
                     ┌───────────────────┐
                     │   用户执行命令      │
                     │  --mode select     │
                     │  --mode specify    │
                     │  --mode resume     │
                     └─────────┬─────────┘
                               │
                ┌──────────────┼──────────────┐
                ▼              ▼              ▼
         ┌─────────┐   ┌─────────┐   ┌──────────┐
         │ select  │   │ specify │   │ resume   │
         │ AI选题  │   │ 指定作品 │   │ 从文件续 │
         └────┬────┘   └────┬────┘   └────┬─────┘
              │              │              │
              ▼              │              │
  ┌────────────────────┐     │              │
  │ Step 0: AI 选题     │     │              │
  │ MODEL_PRO + Search │     │              │
  │ + 记忆系统防重复    │     │              │
  │ → topics.json      │     │              │
  │ → registry.json    │     │              │
  └────────┬───────────┘     │              │
           │                 │              │
           └────────┬────────┘──────────────┘
                    │
                    ▼  (对每部作品循环执行)
   ┌──────────────────────────────────────────┐
   │ Step 0b: 获取原文                          │
   │ 优先级: --text-file > 自动获取 > 终止      │
   │ 数据源: Gutenberg > Wikisource >          │
   │         Standard Ebooks > Internet Archive│
   │         > Open Library > 本地缓存          │
   └────────────────┬─────────────────────────┘
                    │
                    ▼
   ┌──────────────────────────────────────────┐
   │ Step 2: 原文提取地点                       │
   │ MODEL_FLASH + Search                     │
   │ 全文 → 按章节分块 → 6 并发提取 → 合并去重  │
   │ 关键原则: 只提取原文中白纸黑字的地名        │
   └────────────────┬─────────────────────────┘
                    │
                    ▼
   ┌──────────────────────────────────────────┐
   │ Step 3: 结构化富化 + Story Mode           │
   │ MODEL_FLASH_STRUCT (无搜索)               │
   │ 分批处理(5个/批)，传递全局上下文            │
   │ 输出: synopsis, temporal/narrative/cultural│
   │       context, timeline, story_mode       │
   └────────────────┬─────────────────────────┘
                    │
                    ▼
   ┌──────────────────────────────────────────┐
   │ Step 4: 质量自审                           │
   │ MODEL_FLASH_STRUCT                        │
   │ 原著忠实性检查 → 数据质量 → 故事连贯性      │
   │ 移除非原著地点 / 合并重复 / 重编 orderIndex│
   └────────────────┬─────────────────────────┘
                    │
                    ▼
   ┌──────────────────────────────────────────┐
   │ Step 5: 输出                              │
   │ → {pack_id}_places_structured.json        │
   │ → {pack_id}_pipeline_meta.json            │
   │ → registry.json 状态更新为 completed       │
   └────────────────┬─────────────────────────┘
                    │
                    ▼  (手动执行下一步)
   ┌──────────────────────────────────────────┐
   │ 地理编码 (geocode_places.py)              │
   │ Nominatim(国际) / 高德(中国)              │
   │ + 行政区校验 + 距离合理性校验               │
   └────────────────┬─────────────────────────┘
                    │
                    ▼
   ┌──────────────────────────────────────────┐
   │ 打包 (build_pack.py)                      │
   │ → ContentPack v2 JSON                     │
   │ → 导入 iOS 应用                            │
   └──────────────────────────────────────────┘
```

### 🔌 LLM 模型分工

| 模型 | 配置常量 | 用途 | 特点 |
|------|---------|------|------|
| `gemini-3.1-pro-preview-search` | `MODEL_PRO` | 选题 + 搜索原文 | 需要联网 |
| `gemini-3-flash-preview-search` | `MODEL_FLASH` | 批量地点提取 | 需要联网补充知识 |
| `gemini-3-flash-preview` | `MODEL_FLASH_STRUCT` | 结构化 + 审查 | 纯 JSON，不联网 |

---

## 8. 两条工作流对比

### 流程 A: 全自动模式 (推荐)

```bash
# 一条命令搞定：选题→获取原文→提取→结构化→输出
python scripts/auto_pipeline.py --mode select --count 5

# 指定作品
python scripts/auto_pipeline.py --mode specify --work "繁花" --author "金宇澄"

# 手动提供原文
python scripts/auto_pipeline.py --mode specify --work "围城" --author "钱钟书" --text-file ./围城.txt
```

**特点**：`auto_pipeline.py` 内部整合了 Step 0~5，不经过 `processing/` 的合并-清洗-过滤三阶段，而是在 Step 3(结构化) 和 Step 4(审查) 中用 LLM 一次性完成。

### 流程 B: 手动分步模式 (精细控制)

```bash
# 1. 分片
python scripts/split_chapters.py --text novel.txt --out-dir chunks/

# 2. 生成提示词
python scripts/generate_prompts.py --chunks chunks/ --out prompts.jsonl

# 3. LLM 抽取
python scripts/run_extraction.py --prompts prompts.jsonl --out extracted/

# 4. 合并 → 清洗 → 过滤
python scripts/process_data.py --input extracted.jsonl --output ready.jsonl

# 5. 地理编码
python scripts/geocode_places.py --input ready.json --out geocoded.json

# 6. 打包
python scripts/build_pack.py --input geocoded.json --out pack.json --pack-id my-pack
```

**特点**：经过 `merger → cleaner → filter` 三阶段管道，每步可检查中间结果。

### 对比总结

| 维度 | 全自动 (A) | 手动分步 (B) |
|------|-----------|-------------|
| 入口 | `auto_pipeline.py` | 6+ 个脚本 |
| 原文来源 | 自动获取 / --text-file | 用户自备 |
| 数据清洗 | LLM 内联完成 | merger→cleaner→filter |
| 质量控制 | AI 自审 (Step 4) | 人工检查中间文件 |
| 追踪记录 | SQLite 自动记录 | 无 |
| 记忆防重复 | ✅ registry.json | 需手动管理 |
| 适用场景 | 批量生产 | 原文已有、需精细调控 |

---

## 9. 配置与环境变量

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `GEOLORE_API_KEY` | LLM API 密钥 | 必填 |
| `GEOLORE_BASE_URL` | LLM API 端点 | `https://api-k.devdove.site/v1` |
| `GEOLORE_USE_PROXY` | 是否使用系统代理 | `0` (直连) |
| `OPENAI_API_KEY` | 分步脚本的 API Key | — |
| `OPENAI_BASE_URL` | 分步脚本的 API URL | `https://api.openai.com/v1` |
| `AMAP_KEY` | 高德地图 API Key | — |

---

## 10. 当前问题与改进建议

### ✅ 已修复的架构问题（2025-03 重构）

1. **~~两条流水线的重复代码~~** → ✅ 已修复
   - 新增 `src/common/` 模块：`config.py` / `llm_client.py` / `json_utils.py`
   - `auto_pipeline.py`、`recommend_books.py`、`llm_runner.py` 均已改为从 `src.common` 导入
   - 删除了 3 份重复的 `call_llm()`、3 份 `extract_json_from_text()`、3 个 `APIConfig/LLMConfig` 数据类
   - `cleaner.py` 的 `strip_code_fences()` 和 `extract_json_array()` 也统一到 `common.json_utils`

2. **~~`processing/__init__.py` 语法错误~~** → ✅ 已修复
   - 原文件包含裸 markdown 文本（非合法 Python），已改为 docstring

3. **~~API 配置不统一~~** → ✅ 已修复
   - `src/common/config.py` 集中管理环境变量、默认值、模型常量
   - 所有脚本统一使用 `LLMConfig` + `load_llm_config()` 工厂函数

### 🔴 仍需改进的问题

1. **output/ 目录混乱**
   - 多本书的产物混在同一目录，命名规则不统一
   - **建议**：按书名建子目录，如 `output/{slug}/`

2. **地理编码和打包未集成到自动流水线**
   - `auto_pipeline.py` 输出 `places_structured.json` 后就结束了
   - **建议**：将 geocode + build_pack 集成为 Step 6/7

3. **缺少单元测试**
   - 只有一个集成测试 `test_fetch_and_track.py`
   - **建议**：添加 `tests/` 目录，覆盖核心模块

4. **`processing/` 模块在全自动模式中未使用**
   - `merger.py`、`cleaner.py`、`filter.py` 只被手动模式的 `process_data.py` 调用
   - 全自动模式由 LLM 在 Step 3/4 中内联完成相同功能
   - **建议**：考虑是否保留双路径，或统一到一条
