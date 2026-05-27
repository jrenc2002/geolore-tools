#!/usr/bin/env python3
"""繁花流水线运行脚本 — 输出重定向到日志文件"""
import sys, os

# 重定向 stdout/stderr 到日志文件（无缓冲）
log_path = "/tmp/geolore_fanhua.log"
log_f = open(log_path, "w", buffering=1)
sys.stdout = log_f
sys.stderr = log_f

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.common.config import load_llm_config
from scripts.auto_pipeline import run_pipeline_for_work

print("🔧 加载配置...", flush=True)
config = load_llm_config()
print(f"  API Key: {config.api_key[:10]}...", flush=True)
print(f"  Base URL: {config.base_url}", flush=True)
print(f"  Model: {config.model}", flush=True)

print("\n🚀 开始处理《繁花》...", flush=True)
result = run_pipeline_for_work(
    config=config,
    title="繁花",
    author="金宇澄",
    work_type="novel",
    era_setting="1960-1990年代",
    geo_scope="中国上海",
    output_dir="output/books",
    min_places=15,
    tracker=None,
    text_file="output/books/繁花.txt",
)

if result:
    print(f"\n✅ 完成！输出文件: {result}", flush=True)
else:
    print(f"\n❌ 流水线失败", flush=True)
    sys.exit(1)
