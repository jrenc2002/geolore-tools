#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
故实巡礼 · 统一 LLM 客户端

唯一的 LLM 调用入口。提供：
  - OpenAI 兼容协议（/chat/completions）
  - 代理 / 直连智能切换
  - 指数退避重试
  - WAF 拦截自动检测

用法:
    from src.common.config import load_llm_config
    from src.common.llm_client import call_llm

    config = load_llm_config(model="gemini-3-flash-preview")
    text = call_llm(
        messages=[{"role": "user", "content": "hi"}],
        config=config,
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

from src.common.config import LLMConfig, PROVIDER_CLAUDE, PROVIDER_GEMINI, use_proxy

# ─────────────── 请求头模板（规避 WAF） ────────────────

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


def _uses_claude_messages_api(config: LLMConfig) -> bool:
    """Claude 一律走 Anthropic Messages API。"""
    return config.provider == PROVIDER_CLAUDE


def _build_anthropic_messages_payload(
    messages: List[Dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
) -> Dict[str, Any]:
    """将聊天消息转换为 Anthropic Messages API payload。"""
    system_messages = []
    anthropic_messages = []

    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if not content:
            continue
        if role == "system":
            system_messages.append(content)
            continue
        anthropic_messages.append(
            {
                "role": role if role in {"user", "assistant"} else "user",
                "content": content,
            }
        )

    if not anthropic_messages:
        anthropic_messages.append(
            {
                "role": "user",
                "content": "请根据系统指令继续。",
            }
        )

    payload: Dict[str, Any] = {
        "model": model,
        "messages": anthropic_messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if system_messages:
        payload["system"] = "\n\n".join(system_messages)
    return payload


def _extract_anthropic_text(data: Dict[str, Any]) -> str:
    """提取 Anthropic Messages API 的文本内容。"""
    texts: List[str] = []
    for item in data.get("content", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "text":
            continue
        text = item.get("text")
        if isinstance(text, str) and text:
            texts.append(text)

    if texts:
        return "\n".join(texts)

    if "choices" in data:
        return data["choices"][0]["message"]["content"] or ""

    raise RuntimeError(f"无法从 Anthropic Messages 响应中提取文本: {json.dumps(data, ensure_ascii=False)[:500]}")


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

    调用方式直接传入 messages 列表。函数级别的参数可覆盖 config
    中的同名字段（方便同一 config 对象在不同步骤切换模型/温度）。

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

    if _uses_claude_messages_api(config):
        endpoint = config.base_url.rstrip("/") + "/messages"
        payload = _build_anthropic_messages_payload(
            messages=messages,
            model=_model,
            temperature=_temperature,
            max_tokens=_max_tokens,
        )
    else:
        endpoint = config.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": _model,
            "messages": messages,
            "temperature": _temperature,
            "max_tokens": _max_tokens,
        }
        if _expect_json:
            payload["response_format"] = {"type": "json_object"}

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    headers = dict(_BROWSER_HEADERS)
    if _uses_claude_messages_api(config):
        headers["x-api-key"] = config.api_key
        headers["anthropic-version"] = "2023-06-01"
    else:
        headers["Authorization"] = f"Bearer {config.api_key}"

    ctx = ssl.create_default_context()

    if use_proxy():
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx),
            urllib.request.ProxyHandler(),
        )
    else:
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx),
            urllib.request.ProxyHandler({}),  # 空字典 = 忽略系统代理
        )

    for attempt in range(1, config.retry_count + 1):
        try:
            req = urllib.request.Request(
                endpoint, data=body, headers=headers, method="POST"
            )
            with opener.open(req, timeout=config.timeout) as resp:
                raw = resp.read().decode("utf-8")

            # WAF 拦截检测 —— HTML 响应
            if raw.lstrip().startswith("<"):
                snippet = raw[:200].replace("\n", " ")
                raise RuntimeError(
                    f"收到 HTML 响应（可能被代理 WAF 拦截）: {snippet}"
                )

            data = json.loads(raw)
            if _uses_claude_messages_api(config):
                content = _extract_anthropic_text(data)
            else:
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
            if e.code == 503:
                print(
                    "     💡 503 提示：服务端已收到请求，但上游模型暂时不可用；"
                    "这通常不是本地参数错误。"
                )
                if config.provider == PROVIDER_CLAUDE:
                    print(
                        "        当前 Claude 走的是 `/messages` 接口。"
                        "可稍后重试，或临时切换 `--provider gemini`。"
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
                    "        2. 在代理工具中将 api-k.devdove.site 加入直连规则\n"
                    "        3. 在代理服务器端关闭 1Panel WAF 对该域名的过滤"
                )
            if attempt < config.retry_count:
                # 429 限流：等待更长时间
                if "429" in err_str or "Too Many Requests" in err_str:
                    wait = 10.0 * attempt
                    print(f"     🚦 触发限流（429），等待 {wait}s 后重试...")
                else:
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
    from src.common.json_utils import extract_json_from_text  # 延迟导入，避免循环

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
