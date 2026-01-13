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
│   ├── __init__.py
│   ├── extraction/              # 文本信息抽取
│   │   ├── __init__.py
│   │   ├── splitter.py          # 文本分片（按章节）
│   │   ├── prompt_generator.py  # LLM 提示词生成
│   │   └── llm_runner.py        # LLM API 调用
│   ├── geocoding/               # 地理编码
│   │   ├── __init__.py
│   │   ├── nominatim.py         # OSM Nominatim 编码
│   │   ├── amap.py              # 高德地图 API (可选)
│   │   └── validator.py         # 结果验证与校正
│   └── packing/                 # 内容包构建
│       ├── __init__.py
│       └── pack_builder.py      # ContentPack JSON 生成
├── scripts/                     # 命令行入口脚本
│   ├── split_chapters.py        # 文本分片入口
│   ├── generate_prompts.py      # 提示词生成入口
│   ├── run_extraction.py        # LLM 抽取入口
│   ├── geocode_places.py        # 地理编码入口
│   ├── build_pack.py            # 内容包构建入口
│   └── fix_geocode_template.py  # 地理编码修复模板
├── cases/                       # 实战案例
│   ├── beipai-novel/            # 北派盗墓笔记案例
│   └── fanhua-novel/            # 繁花案例
└── examples/                    # 使用示例
    ├── novel/                   # 小说场景处理示例
    └── biography/               # 人物传记处理示例
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 完整流程示例

```bash
# Step 1: 将小说文本分片
python scripts/split_chapters.py \
  --text data/novel.txt \
  --out chunks/ \
  --per-chunk 2

# Step 2: 生成 LLM 提示词
python scripts/generate_prompts.py \
  --chunks chunks/ \
  --out prompts/prompts.jsonl

# Step 3: 调用 LLM 抽取地点信息
python scripts/run_extraction.py \
  --prompts prompts/prompts.jsonl \
  --out extracted/

# Step 4: 地理编码
python scripts/geocode_places.py \
  --extracted extracted/ \
  --cache geocode_cache.json \
  --out geocoded/

# Step 5: 生成内容包
python scripts/build_pack.py \
  --geocoded geocoded/ \
  --pack-id my-novel \
  --title "我的小说地图" \
  --out pack.json
```

## 📚 核心文档

- **[内容包规范](docs/ContentPackSpec.md)** - Geolore iOS 应用使用的 JSON 内容包格式 v2
- **[CloudKit Schema](docs/CloudKitSchema.json)** - iOS 端数据模型定义
- **[地理编码规则](docs/GeocodingRules.md)** - 地址解析的最佳实践
- **[验证机制](docs/ValidationMechanism.md)** - 地理编码结果验证
- **[时间序列规范](docs/TimelineSpec.md)** - 支持按时间顺序浏览的内容包
- **[问题排查](docs/TroubleshootingGuide.md)** - 常见问题与解决方案

## 🎯 LLM Prompt 模板

经过实战验证的提示词模板：

- **[prompts/extraction.md](prompts/extraction.md)** - 地点提取 Chain-of-Thought prompt
- **[prompts/cleaning.md](prompts/cleaning.md)** - 数据批量清洗 prompt

## 🔧 工具说明

### 文本分片器 (Splitter)

将长篇文本按章节分割为便于 LLM 处理的小片段：

- 支持中文章节标题识别（第X章、第X回等）
- 可配置每个分片包含的章节数
- 自动生成索引文件

### LLM 信息抽取

从文本中抽取地点、人物、事件等结构化信息：

- 生成标准化 JSONL 提示词
- 支持多种 LLM API（OpenAI、Claude、自定义）
- 输出结构化 JSON 结果

### 地理编码器 (Geocoder)

将地名转换为经纬度坐标：

- 支持 OSM Nominatim（免费）和高德地图 API
- 分级回退查询策略
- 结果验证与行政区校正
- 本地缓存避免重复请求

### 内容包构建器

将抽取和编码结果打包为 Geolore 格式：

- 符合 ContentPack v2 规范
- 支持时间序列（Timeline）
- 自动去重与合并

## 📖 SOP 文档

- **[标准操作流程 (SOP)](docs/SOP.md)** - 从小说文本到内容包的完整流程

## 📂 实际案例

| 案例 | 类型 | 地点数 | 特点 |
|------|------|--------|------|
| [北派盗墓笔记](cases/beipai-novel/README.md) | 冒险小说 | 942 | 覆盖全国30+省份 |
| [繁花](cases/fanhua-novel/README.md) | 都市小说 | 66 | 聚焦上海，历史街道 |

## 🔗 相关链接

- [Geolore iOS 应用](https://github.com/jrenc2002/geolore)
- [OpenStreetMap Nominatim](https://nominatim.openstreetmap.org/)
- [高德地图 API](https://lbs.amap.com/)

## 📄 License

MIT License
