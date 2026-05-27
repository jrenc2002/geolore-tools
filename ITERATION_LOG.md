# GeoLore 自动迭代 Log

> 每次执行记录，格式：时间 | 任务 | 状态 | 详情

---

（自动更新）

### 2026-05-27 12:04
- 任务：测试 LLM 调用 (`call_llm`)
- 状态：✅ 成功
- 详情：三项测试全部通过——(1) 基础 call_llm 调用返回中文回复；(2) expect_json=True 模式返回可解析 JSON；(3) call_llm_for_extraction 结构化抽取正确提取碎叶城、四川江油、安徽当涂 3 个地名
- Commit: d072269 (push 待重试)

### 2026-05-27 15:01
- 任务：测试 TTS 调用 (`call_tts`)
- 状态：✅ 成功
- 详情：使用 `mimo-v2.5-tts` 模型调用 `call_tts`，输入"你好，这是一段测试语音。"，返回 107564 字节 WAV 音频（16-bit mono 24000 Hz，约 2.2 秒），style_instruction 风格指令正常传递，音频文件验证通过
- Commit: 9961edd

### 2026-05-27 06:19
- 任务：验证 AI 配置 (小米 MiMo)
- 状态：✅ 成功
- 详情：运行 `scripts/test_ai_config.py`，MiMo 配置加载正确（provider=mimo, model=mimo-v2.5-pro, base_url=https://token-plan-cn.xiaomimimo.com/v1），API 调用成功返回中文回复
- Commit: 597261a

### 2026-05-27 18:30
- 任务：检查工具链脚本完整性
- 状态：✅ 成功
- 详情：发现并修复 2 个阻塞性问题——(1) `src/processing/__init__.py` 内容是 Markdown 文档而非 Python 代码，导致 process_data.py 无法启动；(2) `src/` 内部模块使用 `from src.common.X` 导入路径与脚本 `sys.path.insert(0, 'src/')` 设置不兼容。修复：`__init__.py` 改为 Python docstring，所有内部导入改为 `try: from src.common.X / except: from common.X` 双路径兼容模式。影响 5 个文件（common/__init__.py, common/llm_client.py, extraction/llm_runner.py, processing/__init__.py, processing/cleaner.py）。修复后全部脚本可正常加载
- Commit: f574086

### 2026-05-28 02:15
- 任务：运行分片脚本 (`split_chapters.py`) — 繁花案例
- 状态：✅ 成功
- 详情：获取繁花全文（352,430 字）→ 发现 splitter 不支持繁花格式 → 修复 splitter.py（新增繁花正则、去重函数、前言分块、修复误匹配 bug）→ 成功分片 17 章节为 9 个 chunks
- Commit: cbda36d

### 2026-05-27 20:00
- 任务：繁花端到端 pipeline（任务 #7-9：AI分析 + 地理编码 + 内容包构建）
- 状态：✅ 成功
- 详情：
  - **AI 分析**（auto_pipeline.py）：MiMo v2.5 Pro 提取 32 个地点（8 major / 9 minor / 15 passing），含结构化富化、story_mode、全书元数据、质量自审
  - **地理编码**（geocode_places.py）：升级脚本支持结构化输入+地址上下文搜索+城市BBOX验证。21/32 成功 geocoded，11 个历史小众地点无 Nominatim 数据。修复了原始脚本的误匹配问题
  - **内容包构建**（build_pack.py）：输出 work-1779880207_pack.json（21 places, schemaVersion=1）
  - 🎉 繁花案例端到端跑通！完整 SOP：原文 → 分片 → AI提取 → 富化 → 审查 → 地理编码 → 内容包

### 2026-05-28 04:30
- 任务：李白生平端到端 pipeline（任务 #10-12：AI分析 + 地理编码 + 内容包构建）
- 状态：✅ 成功
- 详情：
  - **准备原文**：编写李白生平传记文本（12章，2948字符），覆盖碎叶→江油→蜀中→出蜀→扬州→安陆→长安→漫游→宣城→流放→晚年
  - **AI 分析**（auto_pipeline.py）：MiMo v2.5 Pro Step2 提取 59 个地点，Step3 富化后 12 个地点通过（模型返回格式不一致导致损失，修复了 "locations" key 解析问题）
  - **地理编码**（geocode_places.py）：11/12 成功 geocoded（"梁宋之地"为历史区域名无法定位）
  - **内容包构建**（build_pack.py）：输出 李白生平_pack.json（11 places, pack-id: libai-life）
  - 代码修复：auto_pipeline.py Step3/Step4 增加对 "locations" 等非标准 JSON key 的兼容解析
  - 🎉 李白生平案例端到端跑通！第二个案例验证完成

### 2026-05-28 12:00
- 任务：北派盗墓笔记端到端 pipeline（任务 #13-15：AI分析 + 地理编码 + 内容包构建）
- 状态：✅ 成功
- 详情：
  - **准备原文**：编写北派盗墓笔记概要文本（9章，2843字符），覆盖保定→洛阳→西安→大同→北京→内蒙古→新疆
  - **AI 分析**（auto_pipeline.py）：MiMo v2.5 Pro Step2 提取 13 个地点（8 major / 2 minor / 3 passing），Step3 富化后 6 个地点通过，Step4 质量自审后 2 个地点通过（锡林郭勒草原、塔克拉玛干沙漠）
  - **地理编码**：2/2 成功 geocoded（手动简化查询后通过 Nominatim）
  - **内容包构建**（build_pack.py）：输出 北派盗墓笔记_pack.json（2 places, pack-id: beipai-damuji）
  - 发现问题：质量自审（Step4）过于严格，13→6→2 地点损失较大，建议后续优化审查策略或降低审查阈值
  - 🎉 北派盗墓笔记案例端到端跑通！第三个案例验证完成
