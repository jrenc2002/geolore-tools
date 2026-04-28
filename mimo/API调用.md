模型

MiMo-V2.5-Pro、MiMo-V2.5、MiMo-V2.5-TTS-VoiceClone、MiMo-V2.5-TTS-VoiceDesign、MiMo-V2.5-TTS、MiMo-V2-Pro、MiMo-V2-Omni、MiMo-V2-TTS

额度

700,000,000 Credits

编程工具

支持 OpenClaw、Claude Code、OpenCode、KiloCode 等国内外主流编程工具

其他权益

非高峰期（16:00-24:00 UTC） 0.8x 系数消耗；TTS 系列模型限时免费使用

Token

tp-c4evbam2ttpjibsz93h6sm5all0o3l8qcnsnr5pggrfg8s67

专属 Base URL

兼容 OpenAI 接口协议：
https://token-plan-cn.xiaomimimo.com/v1
兼容 Anthropic 接口协议：
https://token-plan-cn.xiaomimimo.com/anthropic

curl --location --request POST 'BASE_URL/chat/completions' \
--header "api-key: $MIMO_API_KEY" \
--header "Content-Type: application/json" \
--data-raw '{
    "model": "mimo-v2.5-pro",
    "messages": [
        {
            "role": "system",
            "content": "You are MiMo, an AI assistant developed by Xiaomi. Today is date: Tuesday, December 16, 2025. Your knowledge cutoff date is December 2024."
        },
        {
            "role": "user",
            "content": "please introduce yourself"
        }
    ],
    "max_completion_tokens": 1024
}'

curl --location --request POST 'BASE_URL/v1/messages' \
--header "api-key: $MIMO_API_KEY" \
--header "Content-Type: application/json" \
--data-raw '{
    "model": "mimo-v2.5-pro",
    "max_tokens": 1024,
    "system": "You are MiMo, an AI assistant developed by Xiaomi. Today is date: Tuesday, December 16, 2025. Your knowledge cutoff date is December 2024.",
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "please introduce yourself"
                }
            ]
        }
    ]
}'