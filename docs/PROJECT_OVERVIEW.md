# 故实巡礼 (Geolore) · 项目全景文档

> 最后更新：2026-03-03  
> 项目路径：`/Users/jrenc/Downloads/Jrenc_Current_Projects/Geolore/geolore_tools/`

---

## 一、项目是什么

**故实巡礼（Geolore）** 是一款将文学作品中的地点提取为地理坐标、让用户在现实世界中"打卡巡礼"的 iOS 应用。

`geolore_tools` 是其**后端内容生产工具链**，负责：

1. **AI 选书** — 让 AI 推荐高地图价值的文学作品
2. **原文下载** — 从 Anna's Archive 自动下载书籍全文
3. **地点提取** — 用 LLM 从全文提取所有地名，并富化为结构化数据
4. **地理编码** — 将地名转为经纬度坐标
5. **内容打包** — 生成 App 可直接读取的 JSON 内容包

---

## 二、环境配置

### Python 版本

```bash
# 本项目固定使用
/Users/jrenc/.pyenv/versions/3.11.5/bin/python

# 切换版本
pyenv shell 3.11.5
```

### 安装依赖

```bash
cd /Users/jrenc/Downloads/Jrenc_Current_Projects/Geolore/geolore_tools
/Users/jrenc/.pyenv/versions/3.11.5/bin/pip install -r requirements.txt
```

依赖清单（`requirements.txt`）：
```
urllib3>=2.0.0        # HTTP 请求
requests>=2.28.0      # HTTP 请求
aiohttp>=3.8.0        # 异步 HTTP（旧版 cleaner 用）
beautifulsoup4>=4.12.0 # HTML 解析（书籍下载用）
rich>=13.0.0          # 终端美化（可选）
```

### API Keys 和环境配置

所有配置在 `.env` 文件（项目根目录）：

```bash
# Gemini API 配置（主要供应商）
GEMINI_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr
GEMINI_BASE_URL=https://api-k.devdove.site/v1
GEMINI_MODEL=gemini-3.1-pro-preview

# Claude API 配置（次要供应商）
ANTHROPIC_API_KEY=sk-e5b927ff33923bf34ce094329a1db18e8d280392b80d1e332113f054b588d3c4
ANTHROPIC_BASE_URL=https://tokenmax.vip
CLAUDE_MODEL=claude-opus-4-6

# 向后兼容（默认使用 Gemini）
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr
GEOLORE_BASE_URL=https://api-k.devdove.site/v1

# Anna's Archive 配置
ANNAS_ARCHIVE_DOMAIN=https://annas-archive.org
ANNAS_ARCHIVE_DOWNLOAD_DIR=~/Downloads/daily_books
ANNAS_ARCHIVE_TARGET_DOWNLOADS=50

# 可选：高德地图地理编码
# AMAP_KEY=your-amap-key
```

| 变量 | 用途 | 必填 |
|------|------|------|
| `GEMINI_API_KEY` | Gemini LLM 调用（选书 + 地点提取） | ✅ |
| `ANTHROPIC_API_KEY` | Claude LLM 调用（备用供应商） | ✅ |
| `ANNAS_ARCHIVE_DOMAIN` | Anna's Archive 域名 | ✅ |
| `ANNAS_ARCHIVE_DOWNLOAD_DIR` | 书籍下载目录 | ✅ |
| `ANNAS_ARCHIVE_TARGET_DOWNLOADS` | 每日下载目标数量 | ✅ |
| `AMAP_KEY` | 高德地图地理编码（中国地名效果更好） | ❌ |

### AI 供应商架构

项目支持两个 AI 供应商，每日额度独立刷新：

| 供应商 | 用途 | 每日额度 | 配置 |
|--------|------|---------|------|
| **Gemini** | 主要供应商（选书 + 地点提取） | 按 API 配额 | `GEMINI_*` |
| **Claude** | 次要供应商（备用 + 测试） | 按 API 配额 | `ANTHROPIC_*` |

Claude 在本项目中的唯一调用方式：
```text
ANTHROPIC_BASE_URL + /v1/messages
Header: x-api-key, anthropic-version: 2023-06-01
Body: Anthropic Messages API
```

供应商切换：
```python
from src.common.config import load_llm_config, PROVIDER_GEMINI, PROVIDER_CLAUDE

# 使用 Gemini
config = load_llm_config(provider=PROVIDER_GEMINI)

# 使用 Claude
config = load_llm_config(provider=PROVIDER_CLAUDE)
```

### LLM 模型说明

| 模型常量 | 实际模型名 | 用途 |
|---------|-----------|------|
| `MODEL_PRO` | `gemini-3.1-pro-preview-search` | AI 选书推荐（联网搜索） |
| `MODEL_FLASH` | `gemini-3-flash-preview-search` | Step 2 地点提取（联网搜索） |
| `MODEL_FLASH_STRUCT` | `gemini-3-flash-preview` | Step 3/4 结构化富化（纯 JSON） |

> 模型常量定义在 `src/common/config.py`

---

## 三、目录结构

```
geolore_tools/
│
├── scripts/                    ← 所有可执行脚本（见第四节）
│   ├── daily_book_harvest.py   ← ⭐ 每日主入口
│   ├── batch_process_all_books.py ← ⭐ 批量 pipeline
│   ├── recommend_books.py      ← AI 选书
│   ├── fetch_text.py           ← 单本下载
│   ├── auto_pipeline.py        ← 单本完整 pipeline（核心引擎）
│   ├── geocode_places.py       ← 地理编码
│   ├── build_pack.py           ← 打包输出
│   ├── fix_geocode_template.py ← 手动修复坐标模板
│   ├── process_data.py         ← 旧版数据处理（遗留）
│   ├── split_chapters.py       ← 文本分片工具
│   ├── run_extraction.py       ← 旧版 LLM 提取（遗留）
│   ├── generate_prompts.py     ← 旧版 Prompt 生成（遗留）
│   └── test_fetch_and_track.py ← 集成测试
│
├── src/                        ← 核心库模块
│   ├── common/
│   │   ├── config.py           ← LLMConfig、模型常量、环境变量读取
│   │   ├── llm_client.py       ← call_llm() 统一调用入口（含重试）
│   │   └── json_utils.py       ← JSON 从 LLM 回复中提取工具
│   ├── textsource/
│   │   └── fetcher.py          ← fetch_full_text()，Anna's Archive 下载
│   ├── memory/
│   │   └── book_registry.py    ← 注册表 CRUD（load/save/add/build_memory）
│   ├── extraction/
│   │   ├── splitter.py         ← 按章节切分全文
│   │   ├── prompt_generator.py ← 生成地点提取 Prompt
│   │   └── llm_runner.py       ← 批量运行 LLM 提取
│   ├── geocoding/
│   │   ├── nominatim.py        ← OpenStreetMap Nominatim 地理编码
│   │   ├── amap.py             ← 高德地图地理编码
│   │   └── validator.py        ← 坐标验证工具
│   ├── packing/
│   │   └── pack_builder.py     ← 构建 App 内容包
│   ├── processing/
│   │   ├── merger.py           ← 同名地点合并
│   │   ├── cleaner.py          ← LLM 批量清洗
│   │   └── filter.py           ← 无效数据过滤
│   └── tracking/
│       └── tracker.py          ← SQLite 运行追踪数据库
│
├── output/                     ← 所有生成数据
│   ├── books/                  ← 每本书一个子目录（见第五节）
│   ├── data/
│   │   ├── registry.json       ← AI 推荐书目注册表（当前 76 本）
│   │   ├── topics.json         ← 旧版选题文件
│   │   └── scout_archive/      ← 历史 scout 运行记录
│   └── tracking/               ← SQLite 追踪数据库导出
│
├── docs/                       ← 文档目录
│   ├── PROJECT_OVERVIEW.md     ← 📌 本文件
│   ├── scripts_guide.md        ← 脚本命令速查手册
│   ├── SOP.md                  ← 标准操作流程（旧版）
│   ├── ARCHITECTURE.md         ← 系统架构设计
│   ├── ContentPackSpec.md      ← App 内容包格式规范
│   ├── PointSchema.md          ← 地点数据 Schema
│   ├── GeocodingRules.md       ← 地理编码规则
│   ├── TimelineSpec.md         ← 时间线规范
│   ├── ValidationMechanism.md  ← 数据验证机制
│   └── TroubleshootingGuide.md ← 故障排除指南
│
├── requirements.txt            ← Python 依赖
├── .env                        ← API Key 配置（不提交 Git）
└── README.md                   ← 项目简介
```

---

## 四、每日任务管理

### 概述

项目包含三个每日刷新的任务，需要在每天结束前消耗完额度：

1. **Gemini API 额度消耗** - 每日 API 调用配额
2. **Claude API 额度消耗** - 每日 API 调用配额
3. **Anna's Archive 书籍下载** - 每日 50 本下载配额

### 快速启动

#### 方式一：交互式菜单（推荐）

```bash
cd /Users/jrenc/Downloads/JrencsProject/geolore-tools

# 使用 Shell 脚本（交互式菜单）
./scripts/daily_consume.sh

# 或使用 Python 脚本（交互式菜单）
python3 scripts/run_daily_tasks.py
```

#### 方式二：命令行参数

```bash
# 运行所有任务
python3 scripts/run_daily_tasks.py --all

# 只运行 Gemini 任务
python3 scripts/run_daily_tasks.py --gemini

# 只运行 Claude 任务
python3 scripts/run_daily_tasks.py --claude

# 只运行书籍下载任务
python3 scripts/run_daily_tasks.py --books
```

### 单独运行各任务

#### 1. 消耗 Gemini API 额度

```bash
cd /Users/jrenc/Downloads/JrencsProject/geolore-tools
python3 scripts/consume_gemini_api.py
```

**功能：**
- 发送 100 次 API 请求（可在脚本中调整 `TARGET_REQUESTS`）
- 使用多样化的提示词避免重复
- 自动重试失败的请求
- 显示成功/失败统计

**配置：**
- 模型：`GEMINI_MODEL`（默认 `gemini-3.1-pro-preview`）
- 端点：`GEMINI_BASE_URL`
- 密钥：`GEMINI_API_KEY`

#### 2. 消耗 Claude API 额度

```bash
cd /Users/jrenc/Downloads/JrencsProject/geolore-tools
python3 scripts/consume_claude_api.py
```

**功能：**
- 发送 100 次 API 请求（可在脚本中调整 `TARGET_REQUESTS`）
- 使用多样化的提示词
- 自动重试失败的请求
- 显示 token 消耗统计

**配置：**
- 模型：`CLAUDE_MODEL`（默认 `claude-opus-4-6`）
- 端点：`ANTHROPIC_BASE_URL`
- 密钥：`ANTHROPIC_API_KEY`

#### 3. 下载 Anna's Archive 书籍

```bash
cd /Users/jrenc/Downloads/JrencsProject/geolore-tools
python3 scripts/consume_book_downloads.py
```

**功能：**
- 搜索并下载 50 本书籍（可在 `.env` 中调整 `ANNAS_ARCHIVE_TARGET_DOWNLOADS`）
- 自动跳过已下载的书籍
- 支持多种格式（PDF、EPUB、MOBI）
- 显示下载进度和统计

**配置：**
- 域名：`ANNAS_ARCHIVE_DOMAIN`（默认 `https://annas-archive.org`）
- 下载目录：`ANNAS_ARCHIVE_DOWNLOAD_DIR`（默认 `~/Downloads/daily_books`）
- 目标数量：`ANNAS_ARCHIVE_TARGET_DOWNLOADS`（默认 `50`）

### 任务调度建议

#### 使用 cron 自动执行

```bash
# 编辑 crontab
crontab -e

# 添加每日任务（每天晚上 11 点执行）
0 23 * * * cd /Users/jrenc/Downloads/JrencsProject/geolore-tools && python3 scripts/run_daily_tasks.py --all >> /tmp/geolore_daily.log 2>&1
```

#### 手动执行时机

建议在以下时间执行：
- **晚上 11 点前** - 确保在当天结束前消耗完额度
- **早上起床后** - 利用新一天的额度开始工作
- **午休时间** - 让任务在后台运行

### 监控和日志

```bash
# 查看实时日志（如果使用 cron）
tail -f /tmp/geolore_daily.log

# 查看各任务的输出
# Gemini 任务会显示：成功次数、失败次数、响应长度
# Claude 任务会显示：成功次数、失败次数、token 消耗
# 书籍下载会显示：搜索进度、下载进度、文件大小
```

### 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| Gemini API 401 错误 | 额度已用完 | 等待次日额度刷新 |
| Claude API 401 错误 | 额度已用完 | 等待次日额度刷新 |
| 书籍下载失败 | 网络问题或站点限流 | 稍后重试，脚本会自动跳过已下载 |
| 脚本执行缓慢 | 正常现象（有延迟避免限流） | 耐心等待或调整 `DELAY_BETWEEN_REQUESTS` |

---

## 五、脚本详解

### ⭐ `daily_book_harvest.py` — 每日书目收割机

**每天运行一次，把 Anna's Archive 25 本/天的下载配额全部用完。**

完整流程：
```
AI 推荐 25 本（5轮×5本）
    → 按地图价值评分(geo_score)排序
    → 下载前 25 本 txt 到 output/books/
    → 可选：自动触发 batch_process_all_books.py
```

```bash
# 【每日标准命令】AI选书 + 下载 + 自动跑pipeline
cd /Users/jrenc/Downloads/Jrenc_Current_Projects/Geolore/geolore_tools
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python -u scripts/daily_book_harvest.py \
  --auto-pipeline 2>&1 | tee /tmp/geolore_harvest.log

# 只选书，预览推荐列表（不消耗下载配额）
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/daily_book_harvest.py \
  --scout-only

# 【⭐ 查看待下载排名队列】无需API Key，一键查看哪些书还没下载
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/daily_book_harvest.py \
  --show-queue

# 【⭐ 按排名直接下载】跳过AI选书，直接把注册表中未下载的书按评分下载
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python -u scripts/daily_book_harvest.py \
  --download-only 2>&1 | tee /tmp/geolore_dl.log

# 同步注册表状态与磁盘实际文件（修复状态显示异常时用）
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/daily_book_harvest.py \
  --sync-registry

# 偏好特定地区和类型
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/daily_book_harvest.py \
  --prefer-region "日本,东南亚,南美" \
  --prefer-type "travelogue,biography"

# 干跑（只打印计划，不执行）
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/daily_book_harvest.py \
  --dry-run
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--quota` | 25 | 每日下载上限 |
| `--scout-count` | 25 | AI 选书总数 |
| `--scout-batch` | 5 | 每轮 AI 请求本数 |
| `--prefer-region` | 无 | 偏好地区（逗号分隔） |
| `--prefer-type` | 无 | 偏好类型（travelogue/novel/biography/history） |
| `--prefer-language` | 无 | 偏好语言（zh/en/ja 等） |
| `--scout-only` | - | 只选书不下载 |
| `--download-only` | - | 只下载不选书 |
| `--auto-pipeline` | - | 下载后自动跑 pipeline |
| `--dry-run` | - | 只打印不执行 |

---

### ⭐ `batch_process_all_books.py` — 批量 Pipeline

**对 `output/books/` 下所有有 `.txt` 但没有 `_places_structured.json` 的书目，批量跑完整地点提取 pipeline。**

Pipeline 步骤：
```
Step 2: 按章节分块 → 6并发 LLM 提取地名
Step 3: 批量富化（synopsis/story_mode/cultural_tags），BATCH_SIZE=20
Step 3b: 生成全书摘要、人物名册、章节结构
Step 4: QA 审查，REVIEW_BATCH=30
Step 5: 输出 *_places_structured.json + *_pipeline_meta.json
```

```bash
# 【标准命令】处理所有待处理书目
cd /Users/jrenc/Downloads/Jrenc_Current_Projects/Geolore/geolore_tools
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python -u scripts/batch_process_all_books.py \
  --book-concurrency 3 2>&1 | tee /tmp/geolore_batch.log

# 查看进度（另开终端）
tail -f /tmp/geolore_batch.log

# 预览待处理书目（不实际运行）
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/batch_process_all_books.py \
  --dry-run

# 强制重跑某本书（覆盖已有结果）
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/batch_process_all_books.py \
  --force --only in-patagonia

# 只处理指定书目
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/batch_process_all_books.py \
  --only 繁花 长安十二时辰 东京梦华录
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--book-concurrency` | 2 | 同时处理几本书（建议不超过3） |
| `--force` | - | 强制重处理已有结果的书 |
| `--only` | - | 只处理指定 book_id（支持多个） |
| `--dry-run` | - | 只列出待处理书目 |
| `--resume-from` | 自动 | 断点续跑：指定从哪步重跑（`step2`/`step3`/`step3b`/`step4`）。不指定时自动检测 checkpoint 文件跳过已完成步骤 |

**断点续跑机制：**
每步完成后自动在书目目录写入 `_checkpoint_{step}.json`：
- `_checkpoint_step2.json` — Step 2 提取的原始地点列表
- `_checkpoint_step3.json` — Step 3 富化后的地点列表
- `_checkpoint_step3b.json` — Step 3b 全书元数据
- `_checkpoint_step4.json` — Step 4 审查后的地点+报告

中途崩溃后直接重跑原命令即可自动恢复；pipeline 全部完成后 checkpoint 文件自动清除。

```bash
# 中途崩溃后直接重跑（自动从上次断点继续）
GEOLORE_API_KEY=sk-xxx \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python -u scripts/batch_process_all_books.py \
  --only norwegian-wood

# 强制从 Step 3 重跑（丢弃 step3/3b/4 的旧结果，step2 复用）
GEOLORE_API_KEY=sk-xxx \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python -u scripts/batch_process_all_books.py \
  --only norwegian-wood --resume-from step3

# 强制从 Step 4 重跑（只重跑 QA 审查）
GEOLORE_API_KEY=sk-xxx \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python -u scripts/batch_process_all_books.py \
  --only norwegian-wood --resume-from step4
```

---

### `recommend_books.py` — AI 选书

**单独调用 AI 推荐书目，写入 `output/data/registry.json`。**

```bash
# 侦察模式：推荐25本，多轮迭代，按地图价值评分排名
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/recommend_books.py \
  --mode scout --count 25 --batch-size 5

# 单次推荐5本
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/recommend_books.py \
  --count 5

# 查看注册表状态（当前 76 本，其中 completed:14 / recommended:61 / text_pending:1）
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/recommend_books.py --status

# 手动导入外部推荐 JSON
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/recommend_books.py \
  --import-file my_recommendations.json

# 标记某本书状态
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/recommend_books.py \
  --mark "活着" --status completed
```

地图价值评分（geo_score，0-100）权重：

| 维度 | 权重 | 说明 |
|------|------|------|
| 地点密度指数 | 25% | 书中出现地名的密度 |
| 现实可达率 | 20% | 地点在现实中可访问的比例 |
| 巡礼吸引力 | 20% | 读者去实地打卡的意愿 |
| 路线形态 | 10% | linear>network>scattered |
| 受众规模 | 10% | massive>large>medium>niche |

---

### `fetch_text.py` — 单本原文下载

**从 Anna's Archive 下载单本书的原文（epub/txt/pdf → 提取纯文本）。**

```bash
# 下载英文书
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/fetch_text.py \
  --title "The Great Gatsby" --author "F. Scott Fitzgerald" \
  --output output/books/

# 下载中文书（指定语言避免误搜英译本）
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/fetch_text.py \
  --title "活着" --author "余华" --language zh \
  --output output/books/

# 查看已缓存的书目
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/fetch_text.py --list-cache

# 清除缓存重新下载
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/fetch_text.py \
  --title "活着" --no-cache
```

下载流程：书名+作者 → 搜索 Anna's Archive 获取 md5 → Fast Download API → epub/pdf/txt → 提取纯文本 → 缓存

---

### `auto_pipeline.py` — 单本完整 Pipeline（核心引擎）

**`batch_process_all_books.py` 内部调用的核心引擎，也可单独对一本书运行。**

```bash
# 指定模式（不需要原文，AI 联网搜索）
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/auto_pipeline.py \
  --mode specify \
  --work "挪威的森林" \
  --author "村上春树" \
  --work-type novel \
  --era "1960-1970年代" \
  --geo-scope "日本东京"

# 指定原文文件
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/auto_pipeline.py \
  --mode specify \
  --work "繁花" --author "金宇澄" \
  --text-file output/books/繁花/繁花.txt
```

关键参数（在 `auto_pipeline.py` 源码中可调整）：

| 常量 | 当前值 | 说明 |
|------|--------|------|
| `STEP2_CONCURRENCY` | 6 | Step 2 每本书内部并发数 |
| `STEP2_CHAPTERS_PER_CHUNK` | 2 | 每块包含几章 |
| `BATCH_SIZE` | 20 | Step 3 每批富化地点数（改自5） |
| `REVIEW_BATCH` | 30 | Step 4 每批审查地点数（改自15） |
| Step 3 `max_tokens` | 32768 | Step 3 LLM 最大输出（改自8192） |
| Step 4 `max_tokens` | 65536 | Step 4 LLM 最大输出（改自16384） |

---

### `geocode_places.py` — 地理编码

**将 `*_places_structured.json` 中的地名转为经纬度坐标。**

```bash
# 使用 Nominatim（OpenStreetMap，免费，适合国际地点）
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/geocode_places.py \
  --input output/books/dubliners/dubliners_places_structured.json \
  --out output/books/dubliners/dubliners_geocoded.json \
  --cache output/data/geocode_cache.json

# 使用高德地图（中国地名效果更好，需要 AMAP_KEY）
AMAP_KEY=your-key \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/geocode_places.py \
  --input output/books/繁花/繁花_places_structured.json \
  --out output/books/繁花/繁花_geocoded.json \
  --provider amap
```

---

### `fix_geocode_template.py` — 手动修复坐标

**当自动地理编码产生错误坐标时，用此脚本手动校正。**

```bash
# 复制模板，修改 FIX_RULES 后运行
cp scripts/fix_geocode_template.py scripts/fix_繁花.py
# 编辑 fix_繁花.py，在 FIX_RULES 里填入正确坐标
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/fix_繁花.py \
  --input output/books/繁花/繁花_geocoded.json \
  --output output/books/繁花/繁花_geocoded_fixed.json
```

---

### `build_pack.py` — 打包输出

**将地理编码结果打包成 Geolore App 可直接读取的 JSON 内容包。**

```bash
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/build_pack.py \
  --input output/books/dubliners/dubliners_geocoded.json \
  --out output/packs/dubliners_pack.json \
  --pack-id dubliners \
  --title "都柏林人"
```

---

### 遗留脚本（低频使用）

| 脚本 | 用途 |
|------|------|
| `split_chapters.py` | 手动将 txt 按章节切片，输出到 chunks/ 目录 |
| `generate_prompts.py` | 手动生成地点提取 Prompt（.jsonl 格式） |
| `run_extraction.py` | 手动批量运行 LLM 提取（需先用上面脚本生成 prompts） |
| `process_data.py` | 旧版：合并同名地点 + LLM 清洗 + 过滤 |
| `test_fetch_and_track.py` | 集成测试：测试原文获取 + SQLite 追踪数据库 |

---

## 五、数据目录结构

### `output/books/{book_id}/`

每本书在 `output/books/` 下有一个独立目录：

```
output/books/dubliners/
├── Dubliners.txt                        ← 原文全文（pipeline 输入）
├── fetch_meta.json                      ← 下载元数据
├── dubliners_places_structured.json     ← ⭐ 地点提取结果（pipeline 输出）
├── dubliners_pipeline_meta.json         ← pipeline 运行元数据
└── dubliners_geocoded.json              ← 地理编码结果（geocode 后）
```

### `*_places_structured.json` 数据格式

```json
{
  "book_info": {
    "title": "都柏林人",
    "author": "詹姆斯·乔伊斯",
    "work_type": "novel",
    "era_setting": "20世纪初",
    "geo_scope": "爱尔兰都柏林"
  },
  "characters": [...],
  "parts": [
    {
      "part_title": "第一章",
      "summary": "..."
    }
  ],
  "places": [
    {
      "name": "都柏林北奥蒙德码头",
      "name_en": "North Ormond Quay, Dublin",
      "place_type": "street",
      "synopsis": "...",
      "story_mode": "...",
      "cultural_tags": ["爱尔兰", "都市"],
      "chapters": ["The Dead"],
      "coordinates": null
    }
  ]
}
```

### `output/data/registry.json` — AI 选书注册表

记录所有 AI 推荐过的书目（当前 **76 本**）：
- `completed`: 14 本（已提取地点）
- `recommended`: 61 本（已推荐，待下载）
- `text_pending`: 1 本（已下载，待处理）

---

## 六、当前数据进度

### 已完成（23 本，共 1,719 个地点）

| 书目 | 地点数 | 完成时间 |
|------|--------|---------|
| The Shadow of the Wind 《风之影》 | 173 | 03-03 |
| Dubliners 《都柏林人》 | 153 | 03-02 |
| Inferno 《地狱》 | 159 | 03-03 |
| The Da Vinci Code 《达芬奇密码》 | 131 | 03-03 |
| The Motorcycle Diaries 《摩托日记》 | 128 | 03-03 |
| A Moveable Feast 《流动的盛宴》 | 116 | 03-02 |
| Country Driving 《寻路中国》 | 115 | 03-02 |
| Angels & Demons 《天使与魔鬼》 | 119 | 03-02 |
| The Old Capital 《古都》 | 79 | 03-03 |
| work-1772474568 《东京梦华录》 | 79 | 03-03 |
| Midnight in the Garden... | 83 | 03-03 |
| chengnanjiu-shi 《城南旧事》 | 65 | 03-02 |
| The Beach 《海滩》 | 53 | 03-03 |
| work-1772452089/2108 等 | 56/68/26/27/36 | 03-02/03 |
| on-the-road 《在路上》 | 16 | 02-28 |
| around-the-world | 15 | 03-02 |
| weicheng 《围城》 | 15 | 02-28 |
| sherlock-holmes | 6 | 03-02 |
| in-patagonia ⚠️ | 1 (异常) | 03-03 |

> ⚠️ `in-patagonia` 只有 1 个地点，需要用 `--force --only in-patagonia` 重跑

### 待处理（有 txt，未跑 pipeline）

- 东京梦华录、大唐西域记、湘行散记、繁花、老残游记、长安十二时辰（6 本中文书）

---

## 七、完整工作流

```
【每日流程】
─────────────────────────────────────────
1. 运行 daily_book_harvest.py
   → AI 5轮×5本 推荐25本书
   → 按 geo_score 排序
   → 下载前25本 txt 到 output/books/
   → 自动触发 batch_process_all_books.py

2. batch_process_all_books.py 跑 pipeline
   → Step 2: 分块提取地名（6并发）
   → Step 3: LLM 富化（20个/批）
   → Step 3b: 书籍元数据
   → Step 4: QA 审查（30个/批）
   → Step 5: 输出 *_places_structured.json

【后处理（按需）】
─────────────────────────────────────────
3. geocode_places.py → 经纬度坐标
4. fix_geocode_template.py → 手动修正错误坐标
5. build_pack.py → 打包给 App
```

---

## 八、监控和调试

### 查看所有书目处理状态

```bash
for dir in /Users/jrenc/Downloads/Jrenc_Current_Projects/Geolore/geolore_tools/output/books/*/; do
  book=$(basename "$dir")
  json=$(find "$dir" -name "*_places_structured.json" 2>/dev/null | head -1)
  txt=$(find "$dir" -name "*.txt" 2>/dev/null | head -1)
  if [ -n "$json" ]; then
    places=$(/Users/jrenc/.pyenv/versions/3.11.5/bin/python3 -c "import json; d=json.load(open('$json')); print(len(d.get('places', [])))" 2>/dev/null)
    mtime=$(stat -f "%Sm" -t "%m-%d %H:%M" "$json")
    echo "✅ $book | $places 地点 | $mtime"
  elif [ -n "$txt" ]; then
    echo "⏳ $book（有txt，待pipeline）"
  fi
done
```

### 查看实时日志

```bash
# pipeline 进度
tail -f /tmp/geolore_batch.log

# 每日收割进度
tail -f /tmp/geolore_harvest.log
```

### 常见问题

| 错误 | 原因 | 解决 |
|------|------|------|
| `HTTP 401` | API Key 配额耗尽 | 等次日（Key 每日重置） |
| `HTTP 504` | API 网关超时（偶发） | 自动重试3次，通常恢复 |
| `HTTP 422` | 请求格式错误（偶发） | 自动重试，通常恢复 |
| 某书只有1-2个地点 | Step 2 提取失败或章节切分异常 | `--force --only {book_id}` 重跑 |
| 进程中途退出 | 终端 session 断开 | 脚本有跳过已完成逻辑，直接重启即可 |

---

## 九、关键路径速查

| 类型 | 路径 |
|------|------|
| 项目根目录 | `/Users/jrenc/Downloads/Jrenc_Current_Projects/Geolore/geolore_tools/` |
| 所有脚本 | `scripts/` |
| 核心库 | `src/` |
| 书目原文 | `output/books/{slug}/{title}.txt` |
| 地点提取结果 | `output/books/{slug}/{slug}_places_structured.json` |
| AI 推荐注册表 | `output/data/registry.json` |
| 地理编码缓存 | `output/data/geocode_cache.json` |
| App 内容包 | `output/packs/` |
| API Key 配置 | `.env` |
| Python 路径 | `/Users/jrenc/.pyenv/versions/3.11.5/bin/python` |
| 文档目录 | `docs/` |
