# 地理编码验证机制

本文档描述地理编码结果的验证机制，用于防止 API 返回错误的匹配结果。

## 背景

在地点解析过程中，发现高德 API 可能返回错误的匹配结果：

### 实际问题案例

**案例1：杭州博物馆被定位到永嘉县**
```
查询: 浙江省-杭州市-上城区-孤山路25号-杭州博物馆
❌ 错误结果: (28.318616, 120.793515) - 永嘉县孤山中小学
✅ 正确位置应在: 杭州市上城区 (30.24, 120.16)
```

**案例2：猎雁林被定位到江西省**
```
查询: 福建省-南平市-建阳区-水吉镇-猎雁林
❌ 错误结果: (26.409067, 114.58971) - 江西省吉安市雁林村
✅ 正确位置应在: 福建省南平市 (27.41, 118.35)
```

## 验证层级

### 验证1：行政区一致性检查

检查返回的 `locality` 是否与查询的行政区匹配：

```python
def validate_locality(query_address: str, result: dict) -> bool:
    """验证行政区一致性"""
    # 提取查询地址的省级行政区
    query_province = query_address.split('-')[0]
    
    # 检查返回的 formattedAddress 是否包含该省份
    formatted_address = result.get('formattedAddress', '')
    if query_province not in formatted_address:
        return False
    
    # 如果查询包含市级，也检查市级
    parts = query_address.split('-')
    if len(parts) >= 2:
        query_city = parts[1]
        if query_city not in formatted_address:
            # 允许直辖市略过市级检查
            if query_province not in ['北京市', '上海市', '天津市', '重庆市']:
                return False
    
    return True
```

### 验证2：坐标距离合理性检查

计算返回坐标与预期城市中心的距离：

```python
import math

def haversine_distance(coord1: tuple, coord2: tuple) -> float:
    """计算两点间的球面距离（公里）"""
    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return 6371 * c  # 地球半径（公里）

def validate_distance(query_address: str, result: dict, city_centers: dict) -> bool:
    """验证坐标距离合理性"""
    # 获取查询城市的中心坐标
    parts = query_address.split('-')
    city_key = parts[1] if len(parts) >= 2 else parts[0]
    
    if city_key not in city_centers:
        return True  # 无法验证，默认通过
    
    city_center = city_centers[city_key]
    result_coord = (result['latitude'], result['longitude'])
    
    distance = haversine_distance(city_center, result_coord)
    
    # 根据查询层级设置阈值
    level = len(parts)
    max_distance = {
        5: 20,    # 街道/具体地点级：最大20公里
        4: 50,    # 区级：最大50公里
        3: 150,   # 市级：最大150公里
        2: 800,   # 省级：最大800公里
        1: 2000   # 国家级：最大2000公里
    }
    
    threshold = max_distance.get(level, 100)
    return distance <= threshold
```

## 自动回退机制

如果验证失败，自动回退到上一级地址重试：

```python
def geocode_with_validation(address: str, api_client, max_retries: int = 4) -> dict:
    """带验证的地理编码"""
    levels = address.split('-')
    
    for num_levels in range(len(levels), 0, -1):
        # 构建当前级别的查询
        query_parts = levels[:num_levels]
        query = "".join(query_parts)
        city = query_parts[0]
        
        # 调用 API
        result = api_client.search(query, city=city)
        
        if result:
            # 执行验证
            if validate_locality(address, result) and \
               validate_distance(address, result, CITY_CENTERS):
                result['matchLevel'] = len(levels) - num_levels
                result['validationPassed'] = True
                return result
            else:
                print(f"验证失败，回退到上一级...")
                continue
    
    return None
```

## 验证元数据

在输出结果中记录验证信息：

```json
{
  "title": "杭州博物馆",
  "latitude": 30.247583,
  "longitude": 120.154183,
  "validationPassed": true,
  "matchLevel": 0,
  "matchMethod": "amap_scoped_exact"
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|-----|------|------|
| `validationPassed` | boolean | 是否通过验证 |
| `matchLevel` | integer | 匹配级别（0=完整匹配，1=回退1级...） |
| `matchMethod` | string | 匹配方法（amap_scoped_exact, nominatim_fallback, manual_fix） |

## 命令行使用

```bash
# 启用验证（默认）
python scripts/geocode.py \
    --input input.json \
    --output output.json \
    --provider amap \
    --amap-key "YOUR_KEY" \
    --enable-validation \
    --verbose

# 禁用验证（使用原始 API 结果）
python scripts/geocode.py \
    --input input.json \
    --output output.json \
    --provider amap \
    --amap-key "YOUR_KEY" \
    --disable-validation
```

## 处理流程图

```
输入地址
    │
    ▼
构建完整查询
    │
    ▼
调用 API ──────────────────┐
    │                      │
    ▼                      │
验证1: 行政区一致性        │
    │                      │
    ├── 通过 ──▶ 验证2     │
    │                      │
    └── 失败 ──▶ 回退 ─────┘
                │
验证2: 距离合理性
    │
    ├── 通过 ──▶ 返回结果
    │
    └── 失败 ──▶ 回退到上一级
```

## 配置参数

```python
# 距离阈值配置（公里）
DISTANCE_THRESHOLDS = {
    'street': 20,     # 街道/镇级
    'district': 50,   # 区级
    'city': 150,      # 市级
    'province': 800   # 省级
}

# 主要城市中心坐标（用于距离验证）
CITY_CENTERS = {
    '北京市': (39.9042, 116.4074),
    '上海市': (31.2304, 121.4737),
    '杭州市': (30.2741, 120.1551),
    '南京市': (32.0603, 118.7969),
    # ...
}
```
