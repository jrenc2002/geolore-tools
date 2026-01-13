## 内容包 JSON v2 协议（Geolore）

适用：分发"非用户创建"的地图内容（内置或网络拉取）。客户端导入后落到现有模型：`Map / Place / MapPlace`（以及 `Tag/TagLink` 标记来源）。不修改 Schema，仅规定 JSON 与导入语义。

**v2 新增**：时间序列支持（Timeline），用于按顺序浏览地点（如人物生平、小说情节）。核心是 `orderIndex` 序号，日期为可选。

### 顶层结构

```json
{
  "schemaVersion": 2,
  "pack": { ... },
  "map": { ... },
  "places": [ ... ],
  "mapPlaces": [ ... ],
  "placeContents": [ ... ],
  "tags": [ ... ]
}
```

### 字段定义

- `schemaVersion`: number，协议版本（v1 或 v2）。v2 支持时间序列。

- `pack`（包元信息）
  - `id` (string, 必填)：内容包唯一 ID（建议小写字母/数字/中划线/下划线），如 `kyoto-temples`
  - `version` (integer, 必填)：包版本，递增
  - `title` (string, 可选)：包标题
  - `locale` (string, 可选)：BCP-47，如 `zh-Hans`
  - `applyMode` (string, 可选)：导入策略，`merge`（默认）| `replace`
    - `merge`：增量合并，不移除历史条目
    - `replace`：以本包为准，不在包内的旧 MapPlace 将被移除

- `map`（地图集）
  - `id` (string, 可选)：UUID；如提供则作为 `Map.id`
  - `title` (string, 必填)：地图标题
  - `descriptionText` (string, 可选)：描述
  - `defaultLatitude` (number, 可选)：[-90, 90]
  - `defaultLongitude` (number, 可选)：[-180, 180]
  - `defaultZoom` (number, 可选)：推荐 2–20（UI 自行裁剪）

- `places[]`（地点条目）
  - `id` (string, 可选)：UUID；如提供则作为 `Place.id`
  - `clientId` (string, 必填)：包内唯一、稳定键（建议正则 `^[A-Za-z0-9_-]{1,64}$`）
  - `title` (string, 必填)
  - `latitude` (number, 必填)：[-90, 90]
  - `longitude` (number, 必填)：[-180, 180]
  - `formattedAddress` (string, 可选)
  - `locality` (string, 可选)：城市/地区
  - `countryCode` (string, 可选)：ISO 3166-1 alpha-2（如 `JP`）
  - `geohash` (string, 可选)：可省略，由客户端计算
  - `synopsis` (string, 可选)：地点摘要/事件描述（v2 新增）
  - `timeline` (object, 可选/必填)：时间序列信息（v2 新增，见下方详细定义）

- `places[].timeline`（时间序列信息，v2 新增）
  - `orderIndex` (integer, **必填**)：地点在故事/生平中的顺序（从 1 递增），决定用户阅读顺序
  - `dateStart` (string, 可选)：起始日期，格式 `YYYY`、`YYYY-MM` 或 `YYYY-MM-DD`
    - 公元前使用负数，如 `-0221` 表示公元前 221 年
  - `dateEnd` (string, 可选)：结束日期，格式同上

- `mapPlaces[]`（地图-地点桥接与展示）
  - `placeClientId` (string, 必填)：引用 `places[].clientId`
  - `customTitle` (string, 可选)：覆盖展示标题
  - `note` (string, 可选)：备注
  - `orderIndex` (integer, 可选)：排序（建议从 1 递增）
  - `pinStyle` (string, 可选)：标注样式键（客户端约定渲染）

- `placeContents[]`（地点内容块，可选）
  - `clientId` (string, 必填)：块级唯一、稳定键（与 `placeClientId` 共同构成幂等键）
  - `placeClientId` (string, 必填)：引用 `places[].clientId`
  - `type` (string, 必填)：`text` | `image` | `gallery` | `link` | `x-*`
  - `orderIndex` (integer, 可选)：排序（同一 Place 内）
  - `locale` (string, 可选)：BCP-47，如 `zh-Hans`
  - `tags` (string[], 可选)
  - `visibility` (string, 可选)：`public` | `hidden`（默认 `public`）
  - `payload` (object, 必填)：按类型定义（见下）

- `placeContents` 类型与 payload（建议）
  - `text`
    - `format` (string)：`plain` | `markdown`（默认 `plain`）
    - `title` (string, 可选)
    - `text` (string, 必填)
  - `image`
    - `url` (string, 必填)
    - `thumbUrl` (string, 可选)
    - `caption` (string, 可选)
    - `license` (string, 可选)
    - `attribution` (string, 可选)
    - `sourceUrl` (string, 可选)
  - `gallery`
    - `images` (array, 必填)：元素为 `{ url, thumbUrl?, caption? }`，数量 ≥ 1
    - `title` (string, 可选)
  - `link`
    - `url` (string, 必填)
    - `title` (string, 可选)
    - `description` (string, 可选)
    - `iconUrl` (string, 可选)

- `tags[]`（贴到 `Map` 的标签）
  - string 数组（可选），如 `["curated", "pack:kyoto-temples@1"]`

### 约束与校验
- `(pack.id, version)` 唯一；同版本二次导入应幂等。
- `places[].clientId` 在同一包内必须唯一且稳定（跨版本保持不变）。
- 经纬度范围：`latitude ∈ [-90, 90]`；`longitude ∈ [-180, 180]`。
- 若提供 `map.id` 或 `places[].id`，必须为合法 UUID 字符串。
- `mapPlaces[].placeClientId` 必须能在 `places[].clientId` 中命中。

- `placeContents[]` 约束（若提供）：
  - `clientId` 在同一包内必须唯一；`(placeClientId, clientId)` 作为幂等键在同一 Place 下唯一且稳定。
  - 未知 `type`（如以 `x-` 前缀）允许；客户端可忽略；导入器不应报错。

### 导入与幂等语义
1) 版本判断：以 `(pack.id, pack.version)` 判断是否已导入；同版本重复导入应无副作用。
2) Map：更新 `title/description/default*`；未提供字段不覆盖。
3) Place 合并规则（按优先级）：
   - 若提供 `places[].id`（UUID），按 id 精确匹配并更新；
   - 否则按 `places[].clientId` 匹配当前 Map 内既有 Place；
   - 均不命中则创建新 Place；坐标近似（≤5m）且 `locality` 相同可复用。
4) MapPlace：
   - 将解析到的 Place 放入 Map；若已存在则更新 `customTitle/orderIndex/pinStyle`；
   - `applyMode=replace` 时，移除 Map 中未出现在本次 `mapPlaces` 的旧条目（建议软删）。
5) Tag：
   - 若 `tags` 缺省，至少打上 `curated` 与 `pack:<id>@<version>`；
   - 已存在同名 Tag 则复用，否则创建后建立 `TagLink`。

6) PlaceContents（可选扩展）：
   - 当前 v1 导入器忽略 `placeContents` 字段（安全向后兼容，不产生副作用）。
   - 客户端渲染建议：
     - 单条 `text` 可用于覆盖当前 Map 上该地点的展示文案（如详情页概述，或 `MapPlace.note`）；多条按 `orderIndex` 在详情页顺序展示；
     - `image/gallery/link` 由客户端按能力展示（例如首图作为头图、画廊、外链卡片）。
   - 若未来实现导入扩展：建议以 `(placeClientId, clientId)` 为 upsert 主键；`applyMode=replace` 在同一 Place 维度进行块列表替换（建议软删）。

### 错误处理（建议）
- 400：缺少必填字段 / 经纬度非法 / `clientId` 重复 / `mapPlaces` 引用失配。
- 409：相同 `(pack.id, version)` 重复导入但内容摘要不一致（可选校验）。
- 413：单包体量过大（建议上限：`places ≤ 10k`，`mapPlaces ≤ 10k`）。

### 极简示例
```json
{
  "schemaVersion": 1,
  "pack": { "id": "sample-pack", "version": 1 },
  "map": { "title": "示例地图" },
  "places": [
    { "clientId": "p1", "title": "A 点", "latitude": 34.0, "longitude": 135.0 }
  ],
  "mapPlaces": [ { "placeClientId": "p1" } ]
}
```

### 完整示例
```json
{
  "schemaVersion": 1,
  "pack": {
    "id": "kyoto-temples",
    "version": 1,
    "title": "京都寺庙巡礼",
    "locale": "zh-Hans",
    "applyMode": "merge"
  },
  "map": {
    "id": "c9b87c54-1a30-4e63-8a0a-0f9b5a6d1a11",
    "title": "京都寺庙地图",
    "descriptionText": "东山·清水寺周边巡礼",
    "defaultLatitude": 35.003,
    "defaultLongitude": 135.778,
    "defaultZoom": 13
  },
  "places": [
    {
      "id": "8d9f86a2-2e0b-4a3a-bb5c-6fa927f5f21b",
      "clientId": "p1",
      "title": "清水寺",
      "latitude": 34.9949,
      "longitude": 135.785,
      "formattedAddress": "京都市东山区清水1丁目294",
      "locality": "Kyoto",
      "countryCode": "JP"
    },
    {
      "clientId": "p2",
      "title": "三年坂",
      "latitude": 34.9967,
      "longitude": 135.7802
    }
  ],
  "mapPlaces": [
    { "placeClientId": "p1", "customTitle": "清水舞台", "orderIndex": 1, "pinStyle": "temple" },
    { "placeClientId": "p2", "orderIndex": 2 }
  ],
  "tags": ["curated", "pack:kyoto-temples@1"]
}
```

### 扩展示例（含 placeContents）

```json
{
  "schemaVersion": 1,
  "pack": { "id": "kyoto-temples", "version": 2 },
  "map": { "title": "京都寺庙地图" },
  "places": [
    { "clientId": "p1", "title": "清水寺", "latitude": 34.9949, "longitude": 135.785 }
  ],
  "mapPlaces": [
    { "placeClientId": "p1", "customTitle": "清水舞台", "orderIndex": 1, "pinStyle": "temple" }
  ],
  "placeContents": [
    {
      "clientId": "p1-text-001",
      "placeClientId": "p1",
      "type": "text",
      "orderIndex": 1,
      "locale": "zh-Hans",
      "payload": {
        "format": "markdown",
        "title": "看点",
        "text": "最佳观景时间：清晨。\n拍摄机位在舞台左前侧。"
      }
    },
    {
      "clientId": "p1-img-001",
      "placeClientId": "p1",
      "type": "image",
      "orderIndex": 2,
      "payload": {
        "url": "https://example.com/qingshui.jpg",
        "thumbUrl": "https://example.com/qingshui-thumb.jpg",
        "caption": "清水舞台远景"
      }
    }
  ]
}
```

### 时间序列示例（v2）

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
    "descriptionText": "根据《李白传》等学术研究整理的李白行踪地图",
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
      "locality": "绵阳",
      "countryCode": "CN",
      "synopsis": "李白出生地，在此度过童年和少年时期。",
      "timeline": { "orderIndex": 1, "dateStart": "0701", "dateEnd": "0724" }
    },
    {
      "clientId": "emei",
      "title": "峨眉山",
      "latitude": 29.52,
      "longitude": 103.33,
      "locality": "乐山",
      "countryCode": "CN",
      "synopsis": "出蜀前重游峨眉，结识怀一长老。",
      "timeline": { "orderIndex": 2, "dateStart": "0724" }
    },
    {
      "clientId": "jiangling",
      "title": "江陵（今荆州）",
      "latitude": 30.33,
      "longitude": 112.24,
      "locality": "荆州",
      "countryCode": "CN",
      "synopsis": "出三峡后至江陵，拜访司马承祯。",
      "timeline": { "orderIndex": 3, "dateStart": "0725" }
    },
    {
      "clientId": "jinling",
      "title": "金陵（今南京）",
      "latitude": 32.06,
      "longitude": 118.79,
      "locality": "南京",
      "countryCode": "CN",
      "synopsis": "初游金陵，纵情登览。",
      "timeline": { "orderIndex": 4, "dateStart": "0725", "dateEnd": "0726" }
    },
    {
      "clientId": "dangtu",
      "title": "当涂",
      "latitude": 31.57,
      "longitude": 118.49,
      "locality": "马鞍山",
      "countryCode": "CN",
      "synopsis": "晚年客居当涂，广德元年卒于此。",
      "timeline": { "orderIndex": 99, "dateStart": "0762", "dateEnd": "0763" }
    }
  ],
  "mapPlaces": [
    { "placeClientId": "changming", "orderIndex": 1 },
    { "placeClientId": "emei", "orderIndex": 2 },
    { "placeClientId": "jiangling", "orderIndex": 3 },
    { "placeClientId": "jinling", "orderIndex": 4 },
    { "placeClientId": "dangtu", "orderIndex": 99 }
  ],
  "tags": ["curated", "timeline", "pack:libai-life@1"]
}
```

### 无日期的时间序列示例（小说情节）

```json
{
  "schemaVersion": 2,
  "pack": { "id": "novel-journey", "version": 1 },
  "map": { "title": "小说地点" },
  "places": [
    {
      "clientId": "p1",
      "title": "起点城市",
      "latitude": 31.23,
      "longitude": 121.47,
      "synopsis": "主角的故乡，故事开始的地方。",
      "timeline": { "orderIndex": 1 }
    },
    {
      "clientId": "p2",
      "title": "中转站",
      "latitude": 30.25,
      "longitude": 120.17,
      "synopsis": "主角途经此地，遇到重要人物。",
      "timeline": { "orderIndex": 2 }
    },
    {
      "clientId": "p3",
      "title": "目的地",
      "latitude": 29.87,
      "longitude": 121.55,
      "synopsis": "故事高潮发生地。",
      "timeline": { "orderIndex": 3 }
    }
  ],
  "mapPlaces": [
    { "placeClientId": "p1", "orderIndex": 1 },
    { "placeClientId": "p2", "orderIndex": 2 },
    { "placeClientId": "p3", "orderIndex": 3 }
  ]
}
```

---

实现说明：客户端导入器模板位于 `geolore/Data/Import/`，支持从 `Data`/`URL` 导入、`merge/replace` 两种模式、坐标近似去重、`Tag/TagLink` 标记来源、软删除旧条目等。`placeContents` 为可选扩展字段，当前 v1 导入器会忽略（不报错）；客户端可直接解析并渲染，如需导入请按上文扩展语义实现。

**v2 时间序列说明**：`places[].timeline.orderIndex` 为必填，决定地点的阅读顺序；`dateStart`/`dateEnd` 为可选，有日期的内容（如人物传记）可填写，无日期的内容（如小说情节）可省略。v1 导入器会忽略 `timeline` 字段（向后兼容）。


