# 小说场景处理示例

本示例展示如何从小说文本中抽取地点信息并生成内容包。

## 示例数据

假设我们有一部小说 `novel.txt`，包含多个章节。

## 处理流程

### 1. 文本分片

```bash
python scripts/split_chapters.py \
  --text examples/novel/novel.txt \
  --out-dir examples/novel/chunks/ \
  --per-chunk 2
```

### 2. 生成提示词

```bash
python scripts/generate_prompts.py \
  --chunks examples/novel/chunks/ \
  --out examples/novel/prompts.jsonl \
  --template place
```

### 3. LLM 抽取

```bash
export OPENAI_API_KEY="your-api-key"
python scripts/run_extraction.py \
  --prompts examples/novel/prompts.jsonl \
  --out examples/novel/extracted/ \
  --model gpt-4
```

### 4. 聚合抽取结果

抽取结果存储在 `extracted/` 目录下，每个分片对应一个 JSON 文件。

需要编写脚本聚合这些结果，提取唯一的地名列表。

### 5. 地理编码

```bash
python scripts/geocode_places.py \
  --input examples/novel/aggregated_places.json \
  --out examples/novel/geocoded_places.json \
  --cache examples/novel/geocode_cache.json
```

### 6. 生成内容包

```bash
python scripts/build_pack.py \
  --input examples/novel/geocoded_places.json \
  --out examples/novel/novel-pack.json \
  --pack-id my-novel \
  --title "小说地图"
```

## 输出示例

最终生成的 `novel-pack.json` 可直接导入 Geolore iOS 应用。

```json
{
  "schemaVersion": 1,
  "pack": {
    "id": "my-novel",
    "version": 1,
    "title": "小说地图",
    "locale": "zh-Hans",
    "applyMode": "merge"
  },
  "map": {
    "title": "小说地图"
  },
  "places": [
    {
      "clientId": "osm-node-12345",
      "title": "北京故宫",
      "latitude": 39.9163,
      "longitude": 116.3972,
      "locality": "北京",
      "countryCode": "CN"
    }
  ],
  "mapPlaces": [
    {
      "placeClientId": "osm-node-12345",
      "orderIndex": 1
    }
  ],
  "tags": ["curated", "pack:my-novel@1"]
}
```
