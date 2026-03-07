# Geolore Tools 文档索引

本项目文档分为两类：**用户文档**（给人类看）和 **AI文档**（给AI看）。

---

## 📘 用户文档 (user/)

给人类用户看的操作指南、SOP和故障排查：

| 文档 | 说明 |
|------|------|
| [PROJECT_OVERVIEW.md](user/PROJECT_OVERVIEW.md) | 📌 项目全景文档（必读） |
| [ClaudeIntegration.md](user/ClaudeIntegration.md) | Claude 唯一接入方式与排错总结 |
| [SOP.md](user/SOP.md) | 标准操作流程（两条流水线） |
| [scripts_guide.md](user/scripts_guide.md) | 脚本命令速查手册 |
| [AUTO_DOWNLOAD_GUIDE.md](user/AUTO_DOWNLOAD_GUIDE.md) | 自动下载配置指南 |
| [TroubleshootingGuide.md](user/TroubleshootingGuide.md) | 常见问题排查 |

**快速开始：**
1. 先读 [PROJECT_OVERVIEW.md](user/PROJECT_OVERVIEW.md) 了解项目全貌
2. 再看 [scripts_guide.md](user/scripts_guide.md) 学习日常命令
3. 遇到问题查 [TroubleshootingGuide.md](user/TroubleshootingGuide.md)

---

## 🤖 AI文档 (ai/)

给AI看的技术规范、协议和验证规则：

| 文档 | 说明 |
|------|------|
| [ContentPackSpec.md](ai/ContentPackSpec.md) | 内容包JSON v2协议规范 |
| [GeocodingRules.md](ai/GeocodingRules.md) | 地理编码规则与验证机制 |
| [PointSchema.md](ai/PointSchema.md) | 地点数据Schema定义 |
| [TimelineSpec.md](ai/TimelineSpec.md) | 时间序列内容包规范 |
| [ValidationMechanism.md](ai/ValidationMechanism.md) | 地理编码验证机制 |
| [CloudKitSchema.json](ai/CloudKitSchema.json) | iOS CloudKit数据模型 |

**AI使用说明：**
- 这些文档定义了数据格式、验证规则和API协议
- 在生成内容包、地理编码、数据验证时必须遵循这些规范
- 所有规范都是强制性的，不可违反

---

## 文档维护原则

### 用户文档 (user/)
- **目标读者**：人类开发者、运维人员
- **内容特点**：操作步骤、命令示例、故障排查
- **语言风格**：清晰易懂、有实例、有截图
- **更新频率**：功能变更时更新

### AI文档 (ai/)
- **目标读者**：AI助手、自动化脚本
- **内容特点**：技术规范、数据格式、验证规则
- **语言风格**：精确、结构化、无歧义
- **更新频率**：协议变更时更新

---

## 相关链接

- [项目根目录 README](../README.md)
- [Geolore iOS 应用](https://github.com/jrenc2002/geolore)
- [Prompts 模板](../prompts/README.md)
