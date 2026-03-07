# LLM Prompt 模板

本目录包含经过实战验证的 LLM prompt 模板，用于地点数据提取和清洗。

## 模板列表

| 文件 | 用途 | 使用阶段 |
|-----|------|---------|
| `book_recommendation.md` | AI 选书推荐（带记忆防重复）| Stage 0: 选题 |
| `extraction.md` | 从文本中提取地点信息 | Stage 2: AI分析 |
| `cleaning.md` | 清洗和凝练地点数据 | Stage 3: AI汇总 |
| `meta_sop_generator.md` | AI 自动化内容生产工作流 Prompt | 全流程：选题→提取→结构化→审查→输出 |

## 使用流程

```
三种路径：

路径 0（选书推荐，推荐起点）：
  [book_recommendation.md] → AI 推荐适合地理化的书目
       ↓ (结果写入 registry.json)
  recommend_books.py → auto_pipeline.py → 完整生产

路径 1（全自动，推荐）：
  [meta_sop_generator.md] → AI 一次性产出 places_structured.json
       ↓
  geocode_places.py → build_pack.py → content_pack.json

路径 2（分步手动）：
  原始文本 → [extraction.md] → 提取结果 → 合并去重 → [cleaning.md] → 清洗结果
       ↓
  process_data.py → geocode_places.py → build_pack.py → content_pack.json
```

## 记忆系统

`book_recommendation.md` 配合 `scripts/recommend_books.py` 使用记忆系统：

- **registry.json**: 持久化存储所有已推荐/已处理的书目
- 每次推荐时，已有书目列表 + 覆盖统计 + 空白区域提示会自动注入 prompt
- AI 不会重复推荐已有书目，并主动填充未覆盖的地区/类型/语言

## 推荐模型

这些 prompt 已在以下模型上测试通过：

- **GPT-4** / **GPT-4o** - 最佳效果
- **Claude 3** - 效果良好
- **通义千问** - 中文理解较好

## 批量处理

配合 `scripts/` 目录下的脚本使用：

```bash
# 生成批量 prompts
python scripts/generate_prompts.py --input chunks/ --template prompts/extraction.md

# 运行 LLM 提取
python scripts/run_extraction.py --prompts prompts.jsonl --output extracted/
```

## 自定义提示

根据不同类型的内容，可能需要调整 prompt：

### 小说类
- 重点提取：场景描写中的地点
- 过滤：虚构地名

### 历史/传记类
- 重点提取：历史事件发生地
- 需要：古今地名对照

### 游记类
- 重点提取：作者到访的地点
- 保留：主观感受描写
