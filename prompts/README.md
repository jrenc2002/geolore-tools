# LLM Prompt 模板

本目录包含经过实战验证的 LLM prompt 模板，用于地点数据提取和清洗。

## 模板列表

| 文件 | 用途 | 使用阶段 |
|-----|------|---------|
| `extraction.md` | 从文本中提取地点信息 | Stage 2: AI分析 |
| `cleaning.md` | 清洗和凝练地点数据 | Stage 3: AI汇总 |

## 使用流程

```
原始文本 → [extraction.md] → 提取结果 → 合并去重 → [cleaning.md] → 清洗结果
```

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
