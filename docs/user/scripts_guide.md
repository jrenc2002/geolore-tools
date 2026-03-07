# 故实巡礼 · 脚本使用手册

所有脚本均位于：
```
/Users/jrenc/Downloads/Jrenc_Current_Projects/Geolore/geolore_tools/scripts/
```

---

## 环境准备（只需做一次）

```bash
# 进入项目目录
cd /Users/jrenc/Downloads/Jrenc_Current_Projects/Geolore/geolore_tools

# 切换 Python 版本
pyenv shell 3.11.5

# 安装依赖
/Users/jrenc/.pyenv/versions/3.11.5/bin/pip install -r requirements.txt

# 设置 API Key（当前 Key 已写入 .env，也可直接 export）
export GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr
```

以下所有命令均假设你在 `geolore_tools/` 目录下执行，Python 用 `/Users/jrenc/.pyenv/versions/3.11.5/bin/python`（下文简写为 `python`）。

---

## 脚本总览

| 脚本 | 功能 | 使用频率 |
|------|------|---------|
| `daily_book_harvest.py` | **每日主入口**：AI 选书 → 下载原文 → 可选跑 pipeline | 每天 |
| `batch_process_all_books.py` | 批量跑 pipeline（提取 + 富化地点） | 每天 |
| `recommend_books.py` | 单独让 AI 推荐书目，写入注册表 | 按需 |
| `fetch_text.py` | 单独从 Anna's Archive 下载一本书的原文 | 按需 |
| `auto_pipeline.py` | 单本书完整 pipeline（Step 2→5） | 低频 |
| `geocode_places.py` | 对已提取的地点做经纬度地理编码 | pipeline 后 |
| `build_pack.py` | 将地理编码结果打包成 App 可用的 JSON 包 | 最终输出 |
| `process_data.py` | 旧版数据处理流水线（合并+清洗+过滤） | 遗留 |
| `split_chapters.py` | 将 txt 按章节切片（pipeline 内部调用） | 低频 |
| `run_extraction.py` | 旧版 LLM 提取执行工具 | 遗留 |
| `generate_prompts.py` | 旧版 LLM Prompt 生成工具 | 遗留 |
| `fix_geocode_template.py` | 手动修复错误地理编码的模板脚本 | 按需 |
| `test_fetch_and_track.py` | 测试原文获取 + 追踪数据库 | 调试 |

---

## 核心脚本详解

---

### 1. `daily_book_harvest.py` — 每日书目收割机 ⭐

**最重要的脚本，每天用一次，把 25 本下载配额全用完。**

流程：AI 推荐 25 本 → 按评分排序 → 逐一下载 txt → 可选自动跑 pipeline

```bash
# 【标准用法】AI 选书 + 下载 + 自动跑 pipeline（一条命令全搞定）
cd /Users/jrenc/Downloads/Jrenc_Current_Projects/Geolore/geolore_tools
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python -u scripts/daily_book_harvest.py \
  --auto-pipeline 2>&1 | tee /tmp/geolore_harvest.log

# 只让 AI 选书，预览推荐，不消耗下载配额
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/daily_book_harvest.py \
  --scout-only

# 用上次 AI 选的结果直接下载（不重新选书）
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/daily_book_harvest.py \
  --download-only

# 偏好日本、东南亚的游记/传记
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/daily_book_harvest.py \
  --prefer-region "日本,东南亚,南美" --prefer-type "travelogue,biography"

# 干跑：只打印计划，不实际执行
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/daily_book_harvest.py \
  --dry-run
```

输出位置：`output/books/{书名slug}/{书名}.txt` + `fetch_meta.json`

---

### 2. `batch_process_all_books.py` — 批量 Pipeline ⭐

**对所有已下载但未处理的书目，批量跑地点提取 + 富化 + 审查。**

```bash
# 【标准用法】处理所有待处理书目（3 本并发）
cd /Users/jrenc/Downloads/Jrenc_Current_Projects/Geolore/geolore_tools
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python -u scripts/batch_process_all_books.py \
  --book-concurrency 3 2>&1 | tee /tmp/geolore_batch.log

# 查看进度（另开终端）
tail -f /tmp/geolore_batch.log

# 预览哪些书会被处理（不实际运行）
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/batch_process_all_books.py \
  --dry-run

# 强制重新处理某本书（覆盖已有结果）
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/batch_process_all_books.py \
  --force --only in-patagonia

# 只处理指定几本书
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/batch_process_all_books.py \
  --only 繁花 长安十二时辰
```

输出位置：`output/books/{slug}/{slug}_places_structured.json`

---

### 3. `recommend_books.py` — AI 选书

**让 AI 推荐高地图价值书目，结果写入注册表 `output/data/registry.json`。**

```bash
# 侦察模式：AI 推荐 25 本，按地图价值评分排名
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/recommend_books.py \
  --mode scout --count 25

# 查看注册表当前状态
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/recommend_books.py --status

# 推荐 5 本日语书
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/recommend_books.py \
  --count 5 --prefer-language ja --prefer-region "日本"

# 只打印 prompt，不调用 API（方便手动查看或复制）
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/recommend_books.py \
  --dump-prompt --count 5
```

---

### 4. `fetch_text.py` — 单本下载

**从 Anna's Archive 下载单本书的原文。**

```bash
# 下载单本书
GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/fetch_text.py \
  --title "The Great Gatsby" --author "F. Scott Fitzgerald"

# 指定语言（中文书）
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/fetch_text.py \
  --title "活着" --author "余华" --language zh \
  --output output/books/

# 查看本地缓存
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/fetch_text.py --list-cache
```

---

### 5. `geocode_places.py` — 地理编码

**将 `*_places_structured.json` 里的地名转成经纬度坐标。**

```bash
# 对单个文件地理编码
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/geocode_places.py \
  --input output/books/dubliners/dubliners_places_structured.json \
  --out output/books/dubliners/dubliners_geocoded.json \
  --cache output/data/geocode_cache.json

# 修复编码结果中的错误坐标（用模板脚本）
cp scripts/fix_geocode_template.py scripts/fix_geocode_mybook.py
# 编辑 fix_geocode_mybook.py 中的 FIX_RULES，然后运行：
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/fix_geocode_mybook.py \
  --input dubliners_geocoded.json --output dubliners_fixed.json
```

---

### 6. `build_pack.py` — 打包输出

**将地理编码结果打包成 Geolore App 可直接读取的 JSON 包。**

```bash
/Users/jrenc/.pyenv/versions/3.11.5/bin/python scripts/build_pack.py \
  --input output/books/dubliners/dubliners_geocoded.json \
  --out output/packs/dubliners_pack.json \
  --pack-id dubliners \
  --title "都柏林人"
```

---

## 完整工作流（从零到 App）

```
每天一次：
┌─────────────────────────────────────┐
│  daily_book_harvest.py              │  AI选25本 → 下载25本txt
│    └── batch_process_all_books.py   │  提取地点 → 富化 → 审查
└─────────────────────────────────────┘

后处理（按需）：
geocode_places.py    →  经纬度坐标
fix_geocode_template →  手动修正错误坐标
build_pack.py        →  打包给 App
```

---

## 查看处理进度

```bash
# 快速查看所有书的状态（已完成/待处理）
for dir in /Users/jrenc/Downloads/Jrenc_Current_Projects/Geolore/geolore_tools/output/books/*/; do
  book=$(basename "$dir")
  json=$(find "$dir" -name "*_places_structured.json" 2>/dev/null | head -1)
  txt=$(find "$dir" -name "*.txt" 2>/dev/null | head -1)
  if [ -n "$json" ]; then
    places=$(/Users/jrenc/.pyenv/versions/3.11.5/bin/python3 -c "import json; d=json.load(open('$json')); print(len(d.get('places', [])))" 2>/dev/null)
    mtime=$(stat -f "%Sm" -t "%m-%d %H:%M" "$json")
    echo "✅ $book | $places 地点 | $mtime"
  elif [ -n "$txt" ]; then
    echo "⏳ $book (有txt，待处理)"
  fi
done

# 实时查看 pipeline 日志
tail -f /tmp/geolore_batch.log

# 查看今日收割日志
tail -f /tmp/geolore_harvest.log
```

---

## 关键路径速查

| 类型 | 路径 |
|------|------|
| 项目根目录 | `/Users/jrenc/Downloads/Jrenc_Current_Projects/Geolore/geolore_tools/` |
| 所有脚本 | `scripts/` |
| 书目源文本 | `output/books/{slug}/{title}.txt` |
| 提取结果 | `output/books/{slug}/{slug}_places_structured.json` |
| AI 推荐注册表 | `output/data/registry.json` |
| 地理编码缓存 | `output/data/geocode_cache.json` |
| 打包输出 | `output/packs/` |
| API Key 配置 | `.env`（`GEOLORE_API_KEY=...`） |
| Python 路径 | `/Users/jrenc/.pyenv/versions/3.11.5/bin/python` |
