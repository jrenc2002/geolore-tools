#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
故实巡礼 · 统一 LLM / TTS 客户端

唯一的 MiMo API 调用入口。提供：
  - OpenAI 兼容协议（/chat/completions）
  - 代理 / 直连智能切换
  - 指数退避重试
  - TTS 语音合成（mimo-v2.5-tts 系列）

用法:
    from src.common.config import load_llm_config
    from src.common.llm_client import call_llm, call_tts

    config = load_llm_config(model="mimo-v2.5-pro")
    text = call_llm(
        messages=[{"role": "user", "content": "hi"}],
        config=config,
    )

    audio_bytes = call_tts(
        text="要合成的文字",
        config=config,
        style_instruction="用轻快的语调说",
    )
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

try:
    from src.common.config import LLMConfig, use_proxy
except ImportError:
    from common.config import LLMConfig, use_proxy

# ─────────────── 请求头模板 ────────────────

_BROWSER_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}


# ─────────────── 核心调用函数 ─────────────────────────


def _build_opener(ctx: ssl.SSLContext) -> urllib.request.OpenerDirector:
    """构建 HTTP opener，根据代理配置决定是否使用系统代理。"""
    if use_proxy():
        return urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx),
            urllib.request.ProxyHandler(),
        )
    return urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx),
        urllib.request.ProxyHandler({}),  # 空字典 = 忽略系统代理
    )


def call_llm(
    messages: List[Dict[str, str]],
    config: LLMConfig,
    *,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    expect_json: Optional[bool] = None,
) -> str:
    """统一 LLM 调用，返回原始文本内容。

    Args:
        messages:     OpenAI 格式的消息列表
        config:       LLMConfig 实例
        model:        覆盖 config.model
        temperature:  覆盖 config.temperature
        max_tokens:   覆盖 config.max_tokens
        expect_json:  覆盖 config.expect_json

    Returns:
        LLM 返回的原始文本

    Raises:
        RuntimeError: 重试耗尽仍然失败
    """
    _model = model or config.model
    _temperature = temperature if temperature is not None else config.temperature
    _max_tokens = max_tokens if max_tokens is not None else config.max_tokens
    _expect_json = expect_json if expect_json is not None else config.expect_json

    endpoint = config.base_url.rstrip("/") + "/chat/completions"
    payload: Dict[str, Any] = {
        "model": _model,
        "messages": messages,
        "temperature": _temperature,
        "max_tokens": _max_tokens,
    }
    if _expect_json:
        payload["response_format"] = {"type": "json_object"}

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    headers = dict(_BROWSER_HEADERS)
    headers["api-key"] = config.api_key

    ctx = ssl.create_default_context()
    opener = _build_opener(ctx)

    for attempt in range(1, config.retry_count + 1):
        try:
            req = urllib.request.Request(
                endpoint, data=body, headers=headers, method="POST"
            )
            with opener.open(req, timeout=config.timeout) as resp:
                raw = resp.read().decode("utf-8")

            if raw.lstrip().startswith("<"):
                snippet = raw[:200].replace("\n", " ")
                raise RuntimeError(
                    f"收到 HTML 响应（可能被代理 WAF 拦截）: {snippet}"
                )

            data = json.loads(raw)
            content = data["choices"][0]["message"]["content"] or ""
            return content

        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                err_body = ""
            err_str = f"HTTP {e.code}: {err_body or e.reason}"
            print(
                f"  ⚠️  API 调用失败 (尝试 {attempt}/{config.retry_count}): "
                f"{err_str[:200]}"
            )
            if attempt < config.retry_count:
                if e.code == 429:
                    wait = 10.0 * attempt
                elif e.code == 503:
                    wait = max(15.0 * attempt, config.retry_delay * attempt)
                else:
                    wait = config.retry_delay * attempt
                print(f"     等待 {wait}s 后重试...")
                time.sleep(wait)
            else:
                raise RuntimeError(err_str) from e
        except Exception as e:
            err_str = str(e)
            print(
                f"  ⚠️  API 调用失败 (尝试 {attempt}/{config.retry_count}): "
                f"{err_str[:200]}"
            )
            if any(kw in err_str for kw in ("WAF", "HTML", "拦截")):
                print(
                    "     💡 WAF 拦截提示：\n"
                    "        1. 关闭 TUN 模式，改用普通代理模式\n"
                    "        2. 在代理工具中将 token-plan-cn.xiaomimimo.com 加入直连规则"
                )
            if attempt < config.retry_count:
                if "429" in err_str or "Too Many Requests" in err_str:
                    wait = 10.0 * attempt
                    print(f"     🚦 触发限流（429），等待 {wait}s 后重试...")
                else:
                    wait = config.retry_delay * attempt
                    print(f"     等待 {wait}s 后重试...")
                time.sleep(wait)
            else:
                raise


def call_tts(
    text: str,
    config: LLMConfig,
    *,
    model: Optional[str] = None,
    style_instruction: Optional[str] = None,
) -> bytes:
    """调用 MiMo TTS 语音合成，返回音频原始字节。

    按照 MiMo TTS API 规范：
      - 目标文本放在 role=assistant 的消息中
      - 风格指令（自然语言）放在 role=user 的消息中（可选）

    Args:
        text:              要合成的文字内容
        config:            LLMConfig（model 应为 mimo-v2.5-tts 系列）
        model:             覆盖 config.model（建议用 MODEL_TTS 常量）
        style_instruction: 风格/情绪指令，如 "用轻快的语调说"

    Returns:
        音频数据的原始字节（WAV / PCM，取决于服务端返回）

    Raises:
        RuntimeError: 调用失败或重试耗尽
    """
    _model = model or config.model

    messages: List[Dict[str, str]] = []
    if style_instruction:
        messages.append({"role": "user", "content": style_instruction})
    messages.append({"role": "assistant", "content": text})

    endpoint = config.base_url.rstrip("/") + "/chat/completions"
    payload: Dict[str, Any] = {
        "model": _model,
        "messages": messages,
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "api-key": config.api_key,
        "Accept": "*/*",
    }

    ctx = ssl.create_default_context()
    opener = _build_opener(ctx)

    for attempt in range(1, config.retry_count + 1):
        try:
            req = urllib.request.Request(
                endpoint, data=body, headers=headers, method="POST"
            )
            with opener.open(req, timeout=config.timeout) as resp:
                content_type = resp.headers.get("Content-Type", "")
                raw = resp.read()
                # 如果是 JSON 响应，说明返回的是 base64 编码的音频
                if "application/json" in content_type:
                    data = json.loads(raw.decode("utf-8"))
                    import base64
                    audio_b64 = (
                        data.get("audio")
                        or (data.get("choices") or [{}])[0]
                        .get("message", {})
                        .get("audio", {})
                        .get("data", "")
                    )
                    return base64.b64decode(audio_b64)
                # 否则直接是二进制音频
                return raw

        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                err_body = ""
            err_str = f"HTTP {e.code}: {err_body or e.reason}"
            print(f"  ⚠️  TTS 调用失败 (尝试 {attempt}/{config.retry_count}): {err_str[:200]}")
            if attempt < config.retry_count:
                wait = config.retry_delay * attempt
                print(f"     等待 {wait}s 后重试...")
                time.sleep(wait)
            else:
                raise RuntimeError(err_str) from e
        except Exception as e:
            err_str = str(e)
            print(f"  ⚠️  TTS 调用失败 (尝试 {attempt}/{config.retry_count}): {err_str[:200]}")
            if attempt < config.retry_count:
                wait = config.retry_delay * attempt
                print(f"     等待 {wait}s 后重试...")
                time.sleep(wait)
            else:
                raise


# ─────────────── 便捷快捷方式 ─────────────────────────


def call_llm_for_extraction(
    text: str,
    instructions: str,
    schema: dict,
    config: LLMConfig,
) -> Optional[Dict]:
    """面向结构化抽取的便捷包装（兼容旧 llm_runner 签名）。

    自动构建 system + user 消息，返回解析后的 dict；失败返回 None。
    """
    try:
        from src.common.json_utils import extract_json_from_text
    except ImportError:
        from common.json_utils import extract_json_from_text  # 延迟导入，避免循环

    system_prompt = (
        f"{instructions}\n\n"
        "IMPORTANT: You must output ONLY valid JSON. "
        "No markdown code blocks, no explanations.\n"
        f"Strictly follow this schema:\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text},
    ]

    try:
        raw = call_llm(messages, config, expect_json=True)
        result = extract_json_from_text(raw)
        if isinstance(result, dict):
            return result
        print(f"  ⚠️  抽取结果不是对象: {type(result)}")
        return None
    except Exception as e:
        print(f"  ❌  抽取调用失败: {e}")
        return None
