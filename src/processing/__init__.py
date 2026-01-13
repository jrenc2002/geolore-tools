# Processing 模块

数据处理工具，用于清洗、合并和过滤提取的地点数据。

## 模块列表

| 模块 | 功能 |
|-----|------|
| `merger.py` | 合并同名地点，汇总 story |
| `cleaner.py` | 调用 LLM 凝练 synopsis |
| `filter.py` | 过滤无效/宽泛地址 |

## 数据流

```
提取结果 (JSONL)
    │
    ▼
[merger.py] ─── 按 title 分组，合并 story
    │
    ▼
合并结果 (JSON)
    │
    ▼
[cleaner.py] ─── LLM 凝练 synopsis
    │
    ▼
清洗结果 (JSON)
    │
    ▼
[filter.py] ─── 过滤无效数据
    │
    ▼
最终数据 (JSON) → 地理编码
```
