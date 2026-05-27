#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common.config import load_llm_config
from src.common.llm_client import call_tts

# Load config with TTS model
config = load_llm_config(model="mimo-v2.5-tts")

print(f"[INFO] TTS model: {config.model}")
print(f"[INFO] Base URL: {config.base_url}")
print(f"[INFO] Calling TTS...")

try:
    audio_bytes = call_tts(
        text="你好，这是一段测试语音。",
        config=config,
        style_instruction="用自然平和的语调说",
    )
    print(f"[OK] TTS 返回 {len(audio_bytes)} 字节音频数据")
    
    # Save to file for verification
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_tts_output.wav")
    with open(out_path, "wb") as f:
        f.write(audio_bytes)
    print(f"[OK] 已保存到 {out_path}")
except Exception as e:
    print(f"[FAIL] TTS 调用失败: {type(e).__name__}: {e}")
    sys.exit(1)