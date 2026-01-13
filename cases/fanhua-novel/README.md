# 案例：繁花（金宇澄）

本案例展示如何从小说《繁花》中抽取上海地点信息，并生成 Geolore 内容包。

## 📊 项目概况

| 项目 | 数值 |
|------|------|
| 小说名称 | 繁花 |
| 作者 | 金宇澄 |
| 背景城市 | 上海 |
| 时代背景 | 1960-1990年代 |
| 最终地点数 | 66个 |
| 数据源 | 高德地图 API |

## 📁 目录结构

```
繁花/
├── 00_原始小说/
│   └── 繁花.txt
├── 01_分片/
│   ├── chunk_001.txt ~ chunk_XXX.txt
│   └── index.json
├── 02_AI分析/
│   ├── prompts.jsonl
│   └── extract_places.jsonl
├── 03_AI汇总/
│   └── cleaned_places.filtered.shanghai.json
├── 04_地点解析/
│   └── geocoded_places.amap.json
└── 05_内容包/
    └── fanhua-pack.amap.json
```

## 🌆 特点：单城市聚焦

与《北派盗墓笔记》覆盖全国不同，《繁花》的地点全部集中在上海。这带来了：

### 优势
- 地理编码更准确（明确 city=上海市）
- 地点密度高，适合详细浏览
- 可以展示城市变迁

### 挑战
- 部分老地名已不存在
- 需要处理地名演变（如"法租界"→"原法租界"）
- 同一条路可能有多个地点

## 🔧 处理流程

### 阶段 1-2：分片与抽取

与标准流程相同，但提示词针对上海进行了优化：

```markdown
你是一个专业的信息抽取助手。请从《繁花》小说文本中抽取上海地点：

1. 地点类型
   - 街道路名（思南路、淮海路等）
   - 历史建筑（国泰电影院、兰心大戏院等）
   - 餐饮场所（饭店、咖啡馆、小吃店等）
   - 公园/广场
   - 住宅/弄堂

2. 注意事项
   - 所有地点默认在上海市
   - 保留原文中的历史地名
   - 注明现代对应地名（如有）
```

### 阶段 3：数据清洗

针对上海的特殊处理：

```python
# 统一地址前缀
def normalize_shanghai_address(address):
    # 补充上海市前缀
    if not address.startswith("上海"):
        address = f"上海市-{address}"
    
    # 历史地名映射
    mappings = {
        "法租界": "黄浦区/徐汇区/静安区",
        "公共租界": "黄浦区/静安区",
        "南市": "黄浦区",
    }
    
    return address
```

### 阶段 4：地理编码

```bash
# 强制限定在上海市范围内
python scripts/geocode_places.py \
  --input "03_AI汇总/cleaned_places.filtered.shanghai.json" \
  --out "04_地点解析/geocoded_places.amap.json" \
  --provider amap \
  --amap-key "$AMAP_KEY" \
  --default-city "上海市" \
  --validate
```

**关键参数**：`--default-city "上海市"` 确保所有查询都限定在上海范围内。

### 阶段 5：生成内容包

```bash
python scripts/build_pack.py \
  --input "04_地点解析/geocoded_places.amap.json" \
  --out "05_内容包/fanhua-pack.amap.json" \
  --pack-id "fanhua-shanghai" \
  --title "繁花·上海地图" \
  --map-title "金宇澄《繁花》故地巡礼"
```

## 📦 内容包结构

```json
{
  "schemaVersion": 1,
  "pack": {
    "id": "fanhua-shanghai",
    "version": 1,
    "title": "繁花·上海地图",
    "locale": "zh-Hans"
  },
  "map": {
    "title": "金宇澄《繁花》故地巡礼",
    "defaultLatitude": 31.23,
    "defaultLongitude": 121.47,
    "defaultZoom": 12
  },
  "places": [...],
  "mapPlaces": [...],
  "tags": ["curated", "文学", "上海", "pack:fanhua-shanghai@1"]
}
```

## 📊 地点分类统计

### 按类型
| 类型 | 数量 | 示例 |
|------|------|------|
| 历史街道 | 22 | 思南路、瑞金路、复兴中路 |
| 历史建筑 | 18 | 国泰电影院、兰心大戏院 |
| 餐饮场所 | 6 | 云南路热气羊肉店、至真园 |
| 公园/广场 | 8 | 复兴公园、人民广场 |
| 住宅/弄堂 | 7 | 各类里弄 |
| 其他 | 5 | 码头、医院等 |

### 按区域
| 区域 | 数量 |
|------|------|
| 黄浦区 | 28 |
| 徐汇区 | 15 |
| 静安区 | 12 |
| 长宁区 | 6 |
| 其他 | 5 |

## 🗺️ 地图展示

在 Geolore 应用中，繁花地图会：

1. **默认定位到上海市中心**（人民广场附近）
2. **初始缩放级别 12**（可看到主要街道）
3. **地点聚集在市中心**（原租界区域）

用户可以：
- 点击地点查看小说中的描写
- 了解地点的历史背景
- 规划实地探访路线

## 🔑 关键经验

### 1. 单城市项目优化
- 设置 `default-city` 提高编码准确率
- 设置合适的 `defaultZoom` 避免过于缩小
- 地点密集区域考虑聚合显示

### 2. 历史地名处理
- 保留原文地名作为 title
- 在 synopsis 中说明现代对应
- 地址使用现代行政区划

### 3. 地点去重
同一条路可能多次出现：
- 合并为一个地点
- synopsis 包含所有相关情节
- 使用路的中点作为坐标

## 📱 iOS 应用集成

在 `StoreScreen.swift` 中添加：

```swift
contentPackCard(
    title: "繁花",
    subtitle: "金宇澄经典之作",
    description: "漫步1960-1990年代的上海街头，重温阿宝和沪生的青春记忆。66个精选地点，带你领略老上海的繁华与沧桑。",
    systemImage: "building.2.fill",
    status: fanhuaPackStatus,
    isProcessing: isInstallingFanhua,
    action: installFanhuaPack
)
```

## 📚 相关文件

- [完整 SOP 文档](../docs/SOP.md)
- [北派盗墓笔记案例](../cases/beipai-novel/README.md)
- [内容包规范](../docs/ContentPackSpec.md)
