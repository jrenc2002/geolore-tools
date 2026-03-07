# 故实巡礼 · 标准操作流程（SOP）

> 最后更新：2025-07  
> 适用于 geolore-tools 当前架构（含 `src/common/` 统一模块）

---

## 两条流水线概览

| | 全自动 AI 流水线（推荐） | 手动分步流水线 |
|---|---|---|
| 入口 | `auto_pipeline.py` | 各 `scripts/*.py` 逐阶段执行 |
| 适合场景 | 快速批量出内容；无需原文 | 已有原文，需精细控制 |
| 地点来源 | LLM 搜索 + 可选全文补充 | 原文全文 → LLM 抽取 |
| 前置条件 | 只需 `GEOLORE_API_KEY` | 原文 + API Key |

---

## 环境准备

### 安装

```bash
git clone https://github.com/jrenc2002/geolore-tools.git
cd geolore-tools
pip install -r requirements.txt   # requests, aiohttp, rich(可选)
```

### 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `GEOLORE_API_KEY` | ✅ | LLM API 密钥 |
| `GEOLORE_BASE_URL` | ❌ | API 端点（默认 `https://api-k.devdove.site/v1`） |
| `GEOLORE_USE_PROXY` | ❌ | 设为 `1` 使用系统代理，默认直连 |
| `AMAP_KEY` | ❌ | 高德地图 API Key（地理编码用） |

```bash
export GEOLORE_API_KEY="your-api-key"
export AMAP_KEY="your-amap-key"          # 可选
```

### LLM 模型

| 常量 | 模型 | 用途 |
|------|------|------|
| `MODEL_PRO` | `gemini-3.1-pro-preview-search` | 选题 + 搜索（需联网） |
| `MODEL_FLASH` | `gemini-3-flash-preview-search` | 抽取（需联网） |
| `MODEL_FLASH_STRUCT` | `gemini-3-flash-preview` | 结构化 JSON（无联网） |

> 所有模型常量定义在 `src/common/config.py`，函数调用封装在 `src/common/llm_client.py`。

---

## 流水线 A：全自动 AI 流水线

```
┌──────────────────────────────────────────────────────────────────┐
│  Step 0    AI 选题 / 指定作品                                      │
│  Step 0b   自动获取原文（Gutenberg / Wikisource / OL / IA / SE）    │
│  Step 1    LLM 搜索作品资料                                        │
│  Step 2    LLM 批量提取地点（6 并发分块）                             │
│  Step 3    LLM 结构化富化（地址 / synopsis / timeline / storyMode）  │
│  Step 4    LLM 质量自审 + 自动修复                                   │
│  Step 5    输出 places_structured.json + pipeline_meta.json        │
│  ───────── 以下手动执行（命令在 pipeline_meta.next_steps 中）──────── │
│  Step 6    地理编码 → geocode_places.py                            │
│  Step 7    生成内容包 → build_pack.py                               │
└──────────────────────────────────────────────────────────────────┘
```

### A1：AI 自主选题

```bash
python scripts/auto_pipeline.py \
  --mode select \
  --count 5 \
  --output output/
```

| 参数 | 说明 | 默认 |
|------|------|------|
| `--count` | 选题数量 | 5 |
| `--output` | 输出目录 | `output/` |
| `--select-only` | 只选题不生产 | 否 |
| `--min-places` | 最少提取地点数 | 15 |

### A2：指定作品

```bash
python scripts/auto_pipeline.py \
  --mode specify \
  --work "围城" \
  --author "钱钟书" \
  --work-type novel \
  --output output/
```

| 参数 | 说明 | 可选值 |
|------|------|--------|
| `--work` | 作品名称（必填） | — |
| `--author` | 作者（必填） | — |
| `--work-type` | 作品类型 | `novel` / `travelogue` / `biography` / `history` |
| `--era` | 时代背景（提高准确率） | 如 `"1940年代中国"` |
| `--geo-scope` | 地理范围（可选） | 如 `"中国"` |

### A3：AI 选书推荐（带记忆）

```bash
# 推荐 5 本
python scripts/recommend_books.py --count 5

# 推荐完直接进 pipeline
python scripts/recommend_books.py --count 5 --auto-pipeline
```

推荐结果写入 `output/registry.json`，避免重复选题。

### A4：从已有选题恢复

```bash
python scripts/auto_pipeline.py --mode resume --topics-file output/topics.json
```

### 全自动流水线输出

每部作品在 `output/{slug}/` 下生成：

| 文件 | 内容 |
|------|------|
| `{slug}_places_structured.json` | 结构化地点数组 |
| `{slug}_pipeline_meta.json` | 元数据 + `next_steps` 后续命令 |

### Step 6-7：后续手动步骤

从 `pipeline_meta.json` 的 `next_steps` 字段复制命令直接执行：

```bash
# Step 6: 地理编码
python scripts/geocode_places.py \
  --input output/weicheng/weicheng_places_structured.json \
  --out output/weicheng/weicheng_geocoded.json \
  --amap-key $AMAP_KEY \
  --enable-validation

# Step 7: 生成内容包
python scripts/build_pack.py \
  --input output/weicheng/weicheng_geocoded.json \
  --out output/weicheng/weicheng_pack.json \
  --pack-id weicheng \
  --title "《围城》巡礼地图"
```

---

## 流水线 B：手动分步流水线

适合已有原文全文的场景，每步可人工介入调整。

```
Stage 0  原文获取 ─── fetch_text.py
Stage 1  文本分片 ─── split_chapters.py
Stage 2  LLM 提取 ─── generate_prompts.py → run_extraction.py
Stage 3  数据处理 ─── process_data.py（合并 → 清洗 → 过滤）
Stage 4  地理编码 ─── geocode_places.py
Stage 5  生成内容包 ── build_pack.py
```

### Stage 0：原文获取

```bash
python scripts/fetch_text.py \
  --title "Great Expectations" \
  --author "Dickens"
```

支持数据源：Gutenberg / Wikisource / Open Library / Internet Archive / Standard Ebooks

| 参数 | 说明 | 默认 |
|------|------|------|
| `--title` | 作品名称 | 必填（或 `--topics-file`） |
| `--author` | 作者 | — |
| `--language` | 语言代码（zh / en / ja…） | 自动检测 |
| `--sources` | 数据源（逗号分隔） | 全部 |
| `--cache-dir` | 缓存目录 | `output/.text_cache` |

### Stage 1：文本分片

```bash
python scripts/split_chapters.py \
  --text novel.txt \
  --out-dir chunks/ \
  --per-chunk 2
```

### Stage 2：LLM 提取

```bash
# 2a. 生成 prompt
python scripts/generate_prompts.py \
  --input chunks/ \
  --template prompts/extraction.md \
  --output prompts.jsonl

# 2b. 调用 LLM（支持断点续传）
python scripts/run_extraction.py \
  --prompts prompts.jsonl \
  --out extracted/ \
  --api-key $GEOLORE_API_KEY \
  --model gemini-3-flash-preview \
  --rate-limit 1.0
```

### Stage 3：数据处理

```bash
python scripts/process_data.py \
  --input extracted.jsonl \
  --output ready_to_geocode.json \
  --api-key $GEOLORE_API_KEY \
  --batch-size 20 \
  --concurrency 5
```

三步流程：**Merger**（合并同名地点）→ **Cleaner**（LLM 凝练 synopsis）→ **Filter**（过滤无效地址）

> `process_data.py` 是 `merger.py` + `cleaner.py` + `filter.py` 的统一入口。

### Stage 4：地理编码

```bash
# 高德（中国地点推荐）
python scripts/geocode_places.py \
  --input ready_to_geocode.json \
  --out geocoded.json \
  --amap-key $AMAP_KEY \
  --enable-validation

# Nominatim（免费，国际地点）
python scripts/geocode_places.py \
  --input ready_to_geocode.json \
  --out geocoded.json \
  --sleep 1.0
```

> 自动编码不准时用 `scripts/fix_geocode_template.py` 手动修复。

### Stage 5：生成内容包

```bash
python scripts/build_pack.py \
  --input geocoded.json \
  --out pack.json \
  --pack-id my-novel \
  --title "巡礼地图" \
  --schema-version 2
```

---

## 脚本速查表

| 脚本 | 用途 | 所属流水线 |
|------|------|-----------|
| `auto_pipeline.py` | ⭐ 全自动一体化入口 | A |
| `recommend_books.py` | AI 选书推荐（带记忆） | A |
| `fetch_text.py` | 多源原文获取 | A + B |
| `split_chapters.py` | 文本分片 | B |
| `generate_prompts.py` | 生成 prompt JSONL | B |
| `run_extraction.py` | LLM 批量抽取 | B |
| `process_data.py` | 合并 / 清洗 / 过滤 | B |
| `geocode_places.py` | 地理编码 | A + B |
| `build_pack.py` | 生成 ContentPack | A + B |
| `fix_geocode_template.py` | 手动修复编码错误 | 辅助 |
| `test_fetch_and_track.py` | 集成测试 | 开发 |

---

## output 目录结构约定

```
output/
├── registry.json              # 书目注册表（防重复推荐）
├── pipeline_tracker.db        # SQLite 全生命周期追踪
├── topics.json                # 最近一次选题结果
├── .text_cache/               # 原文缓存（自动管理）
│
├── weicheng/                  # 每本书独立目录
│   ├── weicheng_places_structured.json
│   ├── weicheng_pipeline_meta.json
│   ├── weicheng_geocoded.json        # Step 6 后
│   └── weicheng_pack.json            # Step 7 后
├── on-the-road/
└── ...
```

---

## 质量检查清单

### 全自动流水线产出

- [ ] `pipeline_meta.json` 中 `total_places` ≥ 10
- [ ] `address_completeness` = 1.0（所有地点都有地址）
- [ ] `fictional_suspects` = 0（无虚构地名残留）
- [ ] 如有 `story_mode_enabled`，检查章节覆盖率

### 地理编码后

- [ ] 编码成功率 > 95%
- [ ] 无明显跨省 / 跨国错误
- [ ] 验证通过率 > 80%

### 内容包

- [ ] JSON 格式正确
- [ ] `places` 和 `mapPlaces` 数量一致
- [ ] 所有 `placeClientId` 引用有效

---

## 常见问题

### Q: 地理编码失败率高？
- 检查地址格式是否规范
- 中国地点优先用高德（`--amap-key`），国际地点用 Nominatim
- 用 `fix_geocode_template.py` 手动修正

### Q: LLM 返回非 JSON？
- `src/common/json_utils.py` 内置多层容错（code fence 剥离 → 修复 trailing comma → 单引号替换）
- 如果仍然失败，检查 prompt 是否明确要求 JSON 输出

### Q: 全自动流水线中途挂了？
- 已有 SQLite 追踪（`pipeline_tracker.db`），可从 `--mode resume` 恢复
- `run_extraction.py` 也支持断点续传（`--no-skip` 强制重跑）

### Q: 代理设置？
- `GEOLORE_USE_PROXY=1` 会读取系统 `http_proxy` / `https_proxy`
- 默认直连（WAF bypass header 已内置）
