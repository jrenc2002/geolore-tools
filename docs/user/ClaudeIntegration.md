# Claude 唯一接入说明

> 最后更新：2026-03-07

## 结论

本项目里，Claude 只保留一种调用方式：

```text
POST {ANTHROPIC_BASE_URL}/v1/messages
Header: x-api-key: <ANTHROPIC_API_KEY>
Header: anthropic-version: 2023-06-01
Body: Anthropic Messages API
```

代码入口唯一是 `src/common/llm_client.py` 的 `call_llm()`。

---

## 已删除的误导性方式

- `POST /chat/completions`
- `POST /responses`
- `Authorization: Bearer <Claude Key>`
- `ANTHROPIC_AUTH_TOKEN`
- `use_anthropic_format` 配置开关
- `scripts/debug_api.py` 中手写的独立 Claude 请求实现

---

## 当前生效的环境变量

```bash
ANTHROPIC_BASE_URL=https://tokenmax.vip
ANTHROPIC_API_KEY=sk-你的Claude中转Key
CLAUDE_MODEL=claude-sonnet-4-6
```

说明：

- `ANTHROPIC_BASE_URL` 只写基础地址，如 `https://tokenmax.vip`
- 代码会自动规范成 `https://tokenmax.vip/v1`
- 真正请求时自动拼成 `/messages`

---

## 最小验证命令

```bash
cd /Users/jrenc/Downloads/Jrenc_Current_Projects/Geolore/geolore_tools
/Users/jrenc/.pyenv/versions/3.11.5/bin/python -c 'from src.common.config import load_llm_config, PROVIDER_CLAUDE; from src.common.llm_client import call_llm; cfg=load_llm_config(provider=PROVIDER_CLAUDE); print(call_llm([{"role":"user","content":"只回复 pong"}], cfg, max_tokens=32))'
```

预期输出：

```text
pong
```

---

## 这次排查得到的经验

1. `curl` 直测优先级最高。先绕开业务代码，直接验证中转是否能通。
2. Claude 中转和 OpenAI 兼容接口不能混用；同一个 Key 可用，不代表 `/chat/completions` 也可用。
3. 文档、调试脚本、业务代码必须共用同一条实现，否则非常容易出现“文档能通、脚本不能通”的假象。
4. Claude 配置应尽量收敛到 `ANTHROPIC_*`，避免同义环境变量并存。

---

## 相关文件

- `src/common/llm_client.py`
- `src/common/config.py`
- `scripts/test_ai_config.py`
- `scripts/debug_api.py`
- `docs/PROJECT_OVERVIEW.md`
