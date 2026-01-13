# 人物传记处理示例

本示例展示如何从人物传记中抽取时间线事件并生成带时间序列的内容包。

## 适用场景

- 历史人物生平
- 作家/诗人行踪
- 探险家旅程

## 处理流程

### 1. 文本分片

```bash
python scripts/split_chapters.py \
  --text examples/biography/biography.txt \
  --out-dir examples/biography/chunks/ \
  --per-chunk 1
```

人物传记通常章节较短，建议每个分片只包含 1 个章节。

### 2. 生成提示词（使用 timeline 模板）

```bash
python scripts/generate_prompts.py \
  --chunks examples/biography/chunks/ \
  --out examples/biography/prompts.jsonl \
  --template timeline
```

`timeline` 模板会指导 LLM 按时间顺序抽取事件，包含：
- 时间（年份或日期）
- 地点（古今对应）
- 事件摘要
- 原文引用

### 3. LLM 抽取

```bash
export OPENAI_API_KEY="your-api-key"
python scripts/run_extraction.py \
  --prompts examples/biography/prompts.jsonl \
  --out examples/biography/extracted/ \
  --model gpt-4
```

### 4. 聚合与排序

抽取结果需要：
1. 按时间排序
2. 合并同一地点的多个事件
3. 分配 `orderIndex`

### 5. 地理编码

```bash
python scripts/geocode_places.py \
  --input examples/biography/sorted_events.json \
  --out examples/biography/geocoded_events.json \
  --cache examples/biography/geocode_cache.json
```

### 6. 生成内容包（v2 协议）

```bash
python scripts/build_pack.py \
  --input examples/biography/geocoded_events.json \
  --out examples/biography/biography-pack.json \
  --pack-id libai-life \
  --title "李白生平行踪" \
  --schema-version 2
```

## 时间序列数据格式

每个地点需要包含 `timeline` 字段：

```json
{
  "title": "昌明县（今江油）",
  "latitude": 31.78,
  "longitude": 104.75,
  "synopsis": "李白出生地，在此度过童年和少年时期。",
  "timeline": {
    "orderIndex": 1,
    "dateStart": "0701",
    "dateEnd": "0724"
  }
}
```

## 输出示例（v2 协议）

```json
{
  "schemaVersion": 2,
  "pack": {
    "id": "libai-life",
    "version": 1,
    "title": "李白生平行踪",
    "locale": "zh-Hans"
  },
  "map": {
    "title": "李白一生的足迹",
    "defaultLatitude": 34.0,
    "defaultLongitude": 108.0,
    "defaultZoom": 5
  },
  "places": [
    {
      "clientId": "changming",
      "title": "昌明县（今江油）",
      "latitude": 31.78,
      "longitude": 104.75,
      "synopsis": "李白出生地，在此度过童年和少年时期。",
      "timeline": { "orderIndex": 1, "dateStart": "0701", "dateEnd": "0724" }
    },
    {
      "clientId": "emei",
      "title": "峨眉山",
      "latitude": 29.52,
      "longitude": 103.33,
      "synopsis": "出蜀前重游峨眉，结识怀一长老。",
      "timeline": { "orderIndex": 2, "dateStart": "0724" }
    }
  ],
  "mapPlaces": [
    { "placeClientId": "changming", "orderIndex": 1 },
    { "placeClientId": "emei", "orderIndex": 2 }
  ],
  "tags": ["curated", "timeline", "pack:libai-life@1"]
}
```

## iOS 应用中的展示

v2 协议的内容包在 Geolore iOS 应用中会：
1. 按 `orderIndex` 顺序展示地点
2. 支持"下一个/上一个"导航
3. 显示时间信息（如有）
4. 在详情页展示 `synopsis`
