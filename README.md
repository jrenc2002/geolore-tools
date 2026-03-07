# Geolore Tools

地理文学内容数据生成工具集 - 为 [Geolore iOS 应用](https://github.com/jrenc2002/geolore) 生成内容包。

## 📁 项目结构

```
geolore-tools/
├── README.md                    # 本文件
├── requirements.txt             # Python 依赖
├── docs/                        # 规范文档
│   ├── ContentPackSpec.md       # 内容包 JSON v2 协议规范
│   ├── CloudKitSchema.json      # iOS CloudKit 数据模型定义
│   ├── GeocodingRules.md        # 地理编码规则与最佳实践
│   ├── SOP.md                   # 完整工作流 SOP
│   ├── TroubleshootingGuide.md  # 问题排查指南
│   ├── ValidationMechanism.md   # 地理编码验证机制
│   └── TimelineSpec.md          # 时间序列内容包规范
├── prompts/                     # LLM 提示词模板
│   ├── README.md                # 使用说明
│   ├── extraction.md            # 地点提取 prompt
│   └── cleaning.md              # 数据清洗 prompt
├── src/                         # 核心工具代码
│   ├── extraction/              # 文本信息抽取
│   │   ├── splitter.py          # 文本分片（按章节）
│   │   ├── prompt_generator.py  # LLM 提示词生成
│   │   └── llm_runner.py        # LLM API 调用
│   ├── processing/              # 数据处理 ⭐ NEW
│   │   ├── merger.py            # 合并同名地点
│   │   ├── cleaner.py           # LLM 批量清洗 synopsis
│   │   └── filter.py            # 过滤无效数据
│   ├── geocoding/               # 地理编码
│   │   ├── nominatim.py         # OSM Nominatim 编码
│   │   ├── amap.py              # 高德地图 API ⭐ NEW
│   │   └── validator.py         # 结果验证与校正
│   └── packing/                 # 内容包构建
│       └── pack_builder.py      # ContentPack JSON 生成
├── scripts/                     # 命令行入口脚本
│   ├── split_chapters.py        # 文本分片入口
│   ├── generate_prompts.py      # 提示词生成入口
│   ├── run_extraction.py        # LLM 抽取入口
│   ├── process_data.py          # 数据处理入口 (Merge -> Clean -> Filter)
│   ├── geocode_places.py        # 地理编码入口
│   ├── build_pack.py            # 内容包构建入口
│   └── fix_geocode_template.py  # 地理编码修复模板
├── cases/                       # 实战案例
│   ├── beipai-novel/            # 北派盗墓笔记案例
│   └── fanhua-novel/            # 繁花案例
└── examples/                    # 使用示例
    ├── novel/                   # 小说场景处理示例（含数据样例）
    └── biography/               # 人物传记处理示例
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 完整流程（5 个阶段）

```bash
# Stage 1: 文本分片
python src/extraction/splitter.py \
  --input novel.txt \
  --output chunks/ \
  --per-chunk 2
# Stage 2: LLM 提取地点
python scripts/run_extraction.py \
  --prompts prompts.jsonl \
  --out extracted/

# Stage 3: 数据处理 (合并 -> 清洗 -> 过滤) NEW!
python scripts/process_data.py \
  --input extracted.jsonl \
  --output ready_to_geocode.jsonl \
  --api-key $OPENAI_API_KEY

# Stage 4: 地理编码（高德 API）
python scripts/geocode_places.py \
python src/geocoding/amap.py \
  --input filtered.json \
  --output geocoded.json \
  --amap-key YOUR_AMAP_KEY \
  --enable-validation

# Stage 5: 生成内容包
python src/packing/pack_builder.py \
  --input geocoded.json \
  --output pack.json \
  --pack-id my-novel \
  --title "我的小说地图"
```

## 📚 文档导航

文档已按用途分类，方便查找：

### 📘 [用户文档](docs/user/) - 给人类看的操作指南

- [PROJECT_OVERVIEW.md](docs/user/PROJECT_OVERVIEW.md) - 📌 项目全景（必读）
- [scripts_guide.md](docs/user/scripts_guide.md) - 脚本命令速查手册
- [SOP.md](docs/user/SOP.md) - 标准操作流程
- [TroubleshootingGuide.md](docs/user/TroubleshootingGuide.md) - 故障排查指南

### 🤖 [AI文档](docs/ai/) - 给AI看的技术规范

- [ContentPackSpec.md](docs/ai/ContentPackSpec.md) - 内容包JSON v2协议
- [GeocodingRules.md](docs/ai/GeocodingRules.md) - 地理编码规则与验证
- [PointSchema.md](docs/ai/PointSchema.md) - 地点数据Schema
- [TimelineSpec.md](docs/ai/TimelineSpec.md) - 时间序列规范
- [ValidationMechanism.md](docs/ai/ValidationMechanism.md) - 验证机制

**快速开始**：先读 [PROJECT_OVERVIEW.md](docs/user/PROJECT_OVERVIEW.md) 了解项目全貌

## 🎯 LLM Prompt 模板

经过实战验证的提示词模板：

| 模板 | 用途 | 阶段 |
|-----|------|------|
| [extraction.md](prompts/extraction.md) | 地点提取 Chain-of-Thought | Stage 2 |
| [cleaning.md](prompts/cleaning.md) | 数据批量清洗 | Stage 3b |

## 🔧 核心模块

### src/processing/ ⭐ 数据处理

| 模块 | 功能 |
|-----|------|
| `merger.py` | 合并同名地点，汇总 story 数组 |
| `cleaner.py` | 调用 LLM 凝练 synopsis（支持并发、断点续传） |
| `filter.py` | 过滤省级地址、未知标记等无效数据 |

### src/geocoding/ 地理编码

| 模块 | 功能 |
|-----|------|
| `nominatim.py` | OSM Nominatim 免费 API |
| `amap.py` | 高德地图 API（分级回退 + 验证机制） |
| `validator.py` | 结果验证与校正 |

### src/extraction/ 文本抽取

| 模块 | 功能 |
|-----|------|
| `splitter.py` | 按章节分片 |
| `prompt_generator.py` | 生成 LLM prompt |
| `llm_runner.py` | 批量调用 LLM API |

## 📂 实战案例

| 案例 | 类型 | 地点数 | 特点 |
|------|------|--------|------|
| [北派盗墓笔记](cases/beipai-novel/README.md) | 冒险小说 | 942 | 覆盖全国 30+ 省份 |
| [繁花](cases/fanhua-novel/README.md) | 都市小说 | 66 | 聚焦上海，历史街道 |

## 🔗 相关链接

- [Geolore iOS 应用](https://github.com/jrenc2002/geolore)
- [OpenStreetMap Nominatim](https://nominatim.openstreetmap.org/)
- [高德地图 API](https://lbs.amap.com/)

## 📄 License

MIT License
