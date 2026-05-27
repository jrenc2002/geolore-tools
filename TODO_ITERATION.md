# GeoLore 迭代 Todo

> 目标：搭建一套成熟的图书-地点 SOP，让 AI 能自动从书籍中提取地点信息并生成内容包

## 验收标准
- [x] 工具链完整可用（分片 → AI分析 → 汇总 → 地点解析 → 内容包）
- [x] 至少一个案例端到端跑通（繁花 ✅）
- [x] AI 调用统一使用小米 MiMo
- [ ] 输出格式标准化
- [ ] 文档完整

---

## P0 — 工具链验证

- [x] 1. 检查 geolore-tools 依赖安装 (`pip install -r requirements.txt`)
- [x] 2. 验证 AI 配置 (小米 MiMo)
- [x] 3. 测试 LLM 调用 (`call_llm`)
- [x] 4. 测试 TTS 调用 (`call_tts`)
- [x] 5. 检查工具链脚本完整性

## P1 — 案例验证（繁花）✅ 端到端完成

- [x] 6. 运行分片脚本 (`split_chapters.py`)
- [x] 7. 运行 AI 分析+富化+审查 (`auto_pipeline.py` → 32 places extracted, 21 after geocoding)
- [x] 8. 运行地点解析 (`geocode_places.py` → 带城市BBOX验证，21/32 geocoded)
- [x] 9. 运行内容包构建 (`build_pack.py` → work-1779880207_pack.json, 21 places)

> 注：原 TODO 中的 `batch_extract_places.py`/`merge_places_by_title.py`/`geocode_cleaned_places.py`/`build_pack_from_candidates.py` 已被重构为 `auto_pipeline.py` + `geocode_places.py` + `build_pack.py`

## P2 — 案例验证（李白生平）

- [x] 10. 运行李白生平 auto_pipeline
- [x] 11. 运行李白生平地点解析
- [x] 12. 运行李白生平内容包构建

## P3 — 案例验证（北派盗墓笔记）

- [x] 13. 运行北派盗墓笔记 auto_pipeline
- [x] 14. 运行北派盗墓笔记地点解析
- [x] 15. 运行北派盗墓笔记内容包构建

## P4 — iOS 端验证

- [x] 16. 检查 GeoLore iOS 项目结构
- [x] 17. 运行 iOS 单元测试（编译通过，运行受 Xcode 26 beta SwiftData 模拟器 bug 影响）
- [ ] 18. 验证数据加载

## P5 — 文档完善

- [ ] 19. 更新 README
- [ ] 20. 编写 SOP 文档
- [ ] 21. 编写案例文档

## P6 — 工具链改进

- [ ] 22. geocode_places.py 支持高德 API（中文地名更准）
- [ ] 23. 未 geocoded 的地点支持手动坐标补充
- [ ] 24. auto_pipeline.py 输出的 places_structured.json 直接对接 geocode（无需拆分）
