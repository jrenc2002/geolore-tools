"""
Processing 模块 - 数据处理工具，用于清洗、合并和过滤提取的地点数据。

模块列表:
  - merger.py: 合并同名地点，汇总 story
  - cleaner.py: 调用 LLM 凝练 synopsis
  - filter.py: 过滤无效/宽泛地址

数据流:
  提取结果 (JSONL) → merger → cleaner → filter → 地理编码
"""
