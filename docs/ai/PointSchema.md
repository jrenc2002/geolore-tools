# 故实巡礼 · 坐标结构化定义协议

> **核心问题**: 一个"地理坐标点"应该承载什么样的结构化数据，
> 才能既兼容文化信息的厚度，又方便算法检索？

---

## 坐标点数据协议 v2（GeoLore Point Schema）

```
═══════════════════════════════════════════════════════════
一个坐标点 = 空间 × 时间 × 文化 × 叙事
═══════════════════════════════════════════════════════════

这是故实巡礼的底层协议。每个坐标点是一个四维实体：

  ┌─────────────────────────────────────────────────────────┐
  │                    GeoLore Point                         │
  │                                                          │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐│
  │  │  空间层   │  │  时间层   │  │  文化层   │  │  叙事层  ││
  │  │          │  │          │  │          │  │          ││
  │  │ lat/lon  │  │ era      │  │ category │  │ synopsis ││
  │  │ address  │  │ dateStart│  │ themes   │  │ event_lvl││
  │  │ geohash  │  │ dateEnd  │  │ signif.  │  │ chars    ││
  │  │ locality │  │ hist_name│  │ val_bnd  │  │ stay_dur ││
  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘│
  └─────────────────────────────────────────────────────────┘
```

---

## 完整字段定义

### 空间层（Spatial Layer）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | string | ✅ | 地点核心名称 |
| `address` | string | ✅ | 结构化地址：省级-市级-县级-具体地点 |
| `latitude` | number | ⬜ | 纬度 [-90, 90]（由 geocode 填充） |
| `longitude` | number | ⬜ | 经度 [-180, 180]（由 geocode 填充） |
| `formattedAddress` | string | ⬜ | 标准化地址（由 geocode 填充） |
| `locality` | string | ⬜ | 城市/地区 |
| `countryCode` | string | ⬜ | ISO 3166-1 alpha-2 |
| `geohash` | string | ⬜ | GeoHash（客户端计算或预计算） |

### 时间层（Temporal Layer）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `temporal_context.era` | string | ✅ | 时代标签：如"盛唐"、"1990年代"、"二战" |
| `temporal_context.historical_name` | string | ⬜ | 古地名（与今名不同时填写） |
| `temporal_context.date_start` | string | ⬜ | YYYY 或 YYYY-MM-DD，公元前用负数 |
| `temporal_context.date_end` | string | ⬜ | 同上 |

### 文化层（Cultural Layer）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `cultural_tags.category` | enum | ✅ | 见下方枚举 |
| `cultural_tags.themes` | string[] | ✅ | 主题标签（英文），如 ["exile", "war"] |
| `cultural_tags.significance` | number | ✅ | 重要度 0.00-1.00 |
| `cultural_tags.value_boundary` | enum | ⬜ | spatial_narrative / cultural_landmark / route_trace |

**category 枚举**：

| 值 | 中文 | 适用场景 |
|----|------|---------|
| `literary_site` | 文学场所 | 小说中重要场景发生地 |
| `historical_site` | 历史遗址 | 重大历史事件发生地 |
| `poetry_origin` | 诗词创作地 | 诗人在此创作 |
| `poetry_subject` | 诗词吟咏地 | 诗中描写的对象地 |
| `biographical` | 传记足迹 | 人物生平中到过的地方 |
| `travelogue` | 游记地点 | 游记中记录的站点 |
| `folklore` | 民俗传说 | 民间传说/神话关联地 |
| `architectural` | 标志建筑 | 文中重点描写的建筑 |
| `natural_landscape` | 自然景观 | 山川湖海等自然地理 |
| `culinary` | 美食地点 | 与饮食文化相关 |
| `religious` | 宗教场所 | 寺庙、教堂等 |

### 叙事层（Narrative Layer）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `synopsis` | string | ✅ | ≤80字故事摘要，第三人称（用于地图气泡/卡片预览） |
| `narrative_context.event_level` | enum | ✅ | major / minor / passing |
| `narrative_context.characters` | string[] | ⬜ | 相关人物 |
| `narrative_context.stay_duration` | string | ⬜ | 停留时长 |
| `narrative_context.source_chapters` | string[] | ⬜ | 来源章节 |

### 故事模式层（Story Mode Layer）— 让节点串成完整故事

> 这是叙事层的**增强版**，为"故事模式"功能提供沉浸式阅读体验。
> 用户按 orderIndex 顺序浏览各节点时，通过这些字段可以**完整复述整个故事**。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `story_mode.chapter_title` | string | ✅ | 章节标题，如"第三章·黄河路的黄金年代" |
| `story_mode.hook` | string | ✅ | ≤30字悬念钩子，吸引用户点入（如"他在此赚到第一桶金"） |
| `story_mode.narrative_text` | string | ✅ | 200-400字沉浸式叙事文本，让读者仿佛身临其境 |
| `story_mode.transition_to` | string | ⬜ | ≤50字过渡语，引导到下一节点（最后一个节点可省略） |
| `story_mode.mood` | enum | ⬜ | 情绪氛围：tense/nostalgic/joyful/melancholic/dramatic/peaceful/mysterious |
| `story_mode.key_dialogue` | string | ⬜ | 原著中该地点最经典的一句对白或描写（带引号） |
| `story_mode.reading_time_sec` | int | ⬜ | 预估阅读时长（秒），用于 UI 进度条 |

**设计原则**：

```
synopsis     = 地图卡片上的预览（≤80字，像电影海报的一句话介绍）
hook         = 故事模式列表中的钩子（≤30字，像章节预告）
narrative_text = 点进去后的完整叙事（200-400字，像有声书的一段旁白）
transition_to = 读完后引导到下一个地点（像小说的章节尾声）
```

**故事模式的用户体验流**：

```
用户打开"故事模式" →

  📍 节点1: [chapter_title]
     hook: "故事从这里开始..."
     ↓ 点击展开
     [narrative_text] — 200-400字沉浸叙事
     [key_dialogue] — "那一年，上海的霓虹初亮..."
     ↓
     transition_to: "带着对旧日的眷恋，他来到了..."
     → 自动引导到节点2

  📍 节点2: [chapter_title]
     hook: "在这里，命运开始转弯"
     ...

  📍 节点N: [chapter_title]（结局）
     narrative_text 收束全篇
     transition_to: 留空（故事结束）
```

---

## 选题价值边界标准

```
作品是否值得地理化？

              ┌──── 地点密度指数 ≥ 3？────── 否 → ❌ 不推荐
              │
              是
              │
              ├──── 现实可达率 ≥ 60%？────── 否 → ⚠️ 需要评估
              │
              是
              │
              ├──── 属于以下三类之一？
              │     ┌─ 空间叙事型（城市小说/战争/探险）
              │     ├─ 文化地标型（诗词/名著/影视）
              │     └─ 行程轨迹型（游记/传记/朝圣）
              │                                   否 → ❌ 不推荐
              是
              │
              └──── ✅ 推荐选题

不推荐的类型：
  × 纯虚构世界观（奇幻/科幻/仙侠）
  × 地点模糊化（"某市"、"A城"）
  × 已被过度地图化的经典
  × 地理无关的室内/心理叙事
```

---

## 适合地理化的内容类型优先级

```
S 级（天然地理化）:
  ├── 游记/旅行文学  → 自带完整路线
  ├── 传记/回忆录   → 生平足迹就是地图
  ├── 城市小说      → 街道级精度，巡礼感强
  └── 历史纪实      → 事件+地点+时间三维完整

A 级（适合地理化）:
  ├── 地方志/风物志  → 高密度地点，但缺叙事
  ├── 战争文学      → 行军路线清晰，时间线强
  ├── 公路小说      → 线状路线，巡礼感极强
  └── 美食文学      → 地点+文化双重吸引力

B 级（有条件适合）:
  ├── 古典诗词集    → 需要研究创作地，地点分散
  ├── 散文集       → 部分篇章有地理价值
  └── 影视原著     → 取景地+原著地双重地图
```
