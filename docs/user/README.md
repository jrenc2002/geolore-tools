# 用户文档索引

本目录包含所有面向人类用户的操作文档。

---

## 📚 文档列表

### 1. [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) - 项目全景 ⭐ 必读
**适合人群**：所有新用户
**内容**：
- 项目是什么、做什么
- 环境配置（Python、API Keys）
- 目录结构详解
- 每日任务管理
- 脚本详解
- 数据目录结构
- 完整工作流
- 监控和调试

**何时阅读**：第一次接触项目时

---

### 2. [SOP.md](SOP.md) - 标准操作流程
**适合人群**：日常使用者
**内容**：
- 两条流水线概览（全自动 vs 手动分步）
- 环境准备
- 流水线A：全自动AI流水线
- 流水线B：手动分步流水线
- 脚本速查表
- 质量检查清单

**何时阅读**：需要执行完整流程时

---

### 3. [scripts_guide.md](scripts_guide.md) - 脚本使用手册
**适合人群**：日常操作者
**内容**：
- 环境准备（一次性配置）
- 脚本总览表
- 核心脚本详解（带完整命令示例）
- 完整工作流图
- 查看处理进度的方法
- 关键路径速查

**何时阅读**：需要运行具体脚本时

---

### 4. [AUTO_DOWNLOAD_GUIDE.md](AUTO_DOWNLOAD_GUIDE.md) - 自动下载配置
**适合人群**：需要配置自动下载的用户
**内容**：
- Anna's Archive 自动下载配置
- 下载策略和限制
- 故障排查

**何时阅读**：配置自动下载功能时

---

### 5. [TroubleshootingGuide.md](TroubleshootingGuide.md) - 故障排查
**适合人群**：遇到问题的用户
**内容**：
- 常见错误及解决方案
- API错误处理
- 地理编码问题
- 数据质量问题

**何时阅读**：遇到错误或异常时

---

## 🚀 快速开始流程

### 第一次使用
```bash
# 1. 阅读 PROJECT_OVERVIEW.md 了解全貌
# 2. 配置环境（Python + API Keys）
# 3. 运行第一个命令
cd /Users/jrenc/Downloads/Jrenc_Current_Projects/Geolore/geolore_tools
python scripts/daily_book_harvest.py --scout-only
```

### 日常使用
```bash
# 每天运行一次（消耗下载配额）
python scripts/daily_book_harvest.py --auto-pipeline

# 查看进度
tail -f /tmp/geolore_harvest.log
```

### 遇到问题
1. 先查 [TroubleshootingGuide.md](TroubleshootingGuide.md)
2. 检查日志文件 `/tmp/geolore_*.log`
3. 查看 [scripts_guide.md](scripts_guide.md) 确认命令正确

---

## 📖 阅读顺序建议

**新手路径**：
1. PROJECT_OVERVIEW.md（了解全貌）
2. scripts_guide.md（学习命令）
3. SOP.md（理解流程）

**日常使用路径**：
- scripts_guide.md（查命令）
- TroubleshootingGuide.md（排错）

**深度配置路径**：
- AUTO_DOWNLOAD_GUIDE.md（配置下载）
- SOP.md（优化流程）
