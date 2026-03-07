# 时间序列内容包规范

本文档描述支持时间序列浏览的内容包扩展规范。

## 适用场景

- 人物传记（如李白生平）
- 历史事件（如长征路线）
- 旅行游记（按时间顺序的行程）
- 任何需要按特定顺序阅读的内容

## 时间序列特性

时间序列内容包的特点：

1. **每个地点有序号** - `orderIndex` 决定阅读顺序（必填）
2. **日期为可选** - 有明确年份的可填写 `dateStart`/`dateEnd`
3. **支持时间线浏览** - 用户可按顺序阅读

## 数据结构

### timeline 字段

每个地点可包含 `timeline` 字段：

```json
{
  "clientId": "p001",
  "title": "绵州昌明县",
  "latitude": 31.78,
  "longitude": 104.75,
  "synopsis": "李白出生地，在此度过童年和少年时期...",
  "timeline": {
    "orderIndex": 1,
    "dateStart": "0701",
    "dateEnd": "0724"
  }
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `orderIndex` | integer | ✅ | 阅读顺序，从 1 递增 |
| `dateStart` | string | ❌ | 起始年份/日期 |
| `dateEnd` | string | ❌ | 结束年份/日期 |

### 日期格式

支持多种日期精度：

| 格式 | 示例 | 说明 |
|-----|------|------|
| `YYYY` | `"0701"` | 仅年份 |
| `YYYY-MM` | `"0701-01"` | 年月 |
| `YYYY-MM-DD` | `"0701-01-15"` | 完整日期 |

**公元前年份**: 使用负数或 "BC" 后缀
- `"-0044"` 或 `"0044BC"` 表示公元前44年

## 完整内容包示例

```json
{
  "version": "2.0",
  "metadata": {
    "id": "libai-timeline",
    "title": "李白生平",
    "author": "故实巡礼",
    "description": "根据安旗《李白传》整理李白一生的行踪轨迹",
    "timelineEnabled": true
  },
  "places": [
    {
      "clientId": "p001",
      "title": "绵州昌明县",
      "latitude": 31.78,
      "longitude": 104.75,
      "synopsis": "李白出生地，在此度过童年和少年时期，受到良好的文学启蒙教育。",
      "timeline": {
        "orderIndex": 1,
        "dateStart": "0701",
        "dateEnd": "0724"
      }
    },
    {
      "clientId": "p002",
      "title": "成都",
      "latitude": 30.57,
      "longitude": 104.07,
      "synopsis": "李白初出蜀地，在成都短暂停留，结交文人墨客。",
      "timeline": {
        "orderIndex": 2,
        "dateStart": "0724"
      }
    },
    {
      "clientId": "p003",
      "title": "江陵",
      "latitude": 30.33,
      "longitude": 112.24,
      "synopsis": "出三峡后到达江陵，开始其漫游生涯。",
      "timeline": {
        "orderIndex": 3,
        "dateStart": "0724"
      }
    }
  ]
}
```

## 年号换算参考

处理中国古代历史数据时，常需要进行年号换算：

| 年号 | 公元年份 | 说明 |
|------|---------|------|
| 长安元年 | 701 | 李白出生 |
| 开元元年 | 713 | 唐玄宗开元盛世开始 |
| 开元十二年 | 724 | 李白出蜀 |
| 开元十八年 | 730 | 李白初入长安 |
| 天宝元年 | 742 | 李白奉诏入京 |
| 天宝三载 | 744 | 李白赐金放还 |
| 至德二载 | 757 | 李白流放夜郎 |
| 乾元二年 | 759 | 李白遇赦 |
| 广德元年 | 763 | 李白卒于当涂 |

## iOS 客户端支持

### 数据模型扩展

```swift
struct Timeline: Codable {
    let orderIndex: Int
    let dateStart: String?
    let dateEnd: String?
}

struct Place: Codable {
    let clientId: String
    let title: String
    let latitude: Double
    let longitude: Double
    let synopsis: String
    let timeline: Timeline?
}
```

### 时间线视图

客户端可提供：
- 按 `orderIndex` 排序的列表视图
- 地图上的路线连线
- 时间轴滑块控件

## 处理流程

### 1. 数据提取时记录时间信息

在 LLM 提取阶段，prompt 中增加时间提取要求：

```
提取每个地点出现的年份/年代信息。
对于中国古代年号，换算为公元年份。
```

### 2. 清洗时保留时间字段

```json
{
  "title": "长安",
  "address": "陕西省-西安市-长安区",
  "synopsis": "李白初入长安，求取功名...",
  "year": "730"
}
```

### 3. 打包时生成 timeline

```python
def add_timeline(places: list) -> list:
    """为地点列表添加时间线信息"""
    # 按年份排序
    sorted_places = sorted(places, key=lambda p: p.get('year', '9999'))
    
    for idx, place in enumerate(sorted_places, start=1):
        place['timeline'] = {
            'orderIndex': idx,
            'dateStart': place.get('year')
        }
        # 移除临时字段
        place.pop('year', None)
    
    return sorted_places
```

## 注意事项

1. **orderIndex 必须连续**: 从 1 开始，不能有间隔
2. **同一地点多次出现**: 每次出现作为独立条目，有不同的 orderIndex
3. **日期不确定时**: 可只填 orderIndex，省略 dateStart/dateEnd
4. **跨年事件**: 同时填写 dateStart 和 dateEnd
