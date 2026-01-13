# 地理编码问题排查指南

本文档总结了在实际项目中遇到的地理编码问题及其解决方案。

## 常见问题

### 1. 同名地点冲突

**问题描述**: 全国有多个同名地点，API 返回了错误的那个。

**典型案例**:
- "通州" → 期望北京通州，返回南通通州
- "复兴公园" → 期望上海黄浦，返回河北某地

**解决方案**:

```python
# ❌ 错误：只用地点名称查询
result = amap_search("复兴公园")

# ✅ 正确：使用完整地址 + city 限制
result = amap_search(
    keywords="复兴公园 复兴中路",
    city="上海",
    citylimit=True  # 关键！限制搜索范围
)
```

### 2. city 参数使用错误

**问题描述**: 将街道名作为 city 参数传入，API 无法识别。

**典型案例**:
```
地址: 北京市-西城区-广安门外大街-广安门桥
❌ 错误: city="广安门外大街"
✅ 正确: city="北京市" 或 city="西城区"
```

**解决方案**: 分级回退原则

```python
# 从完整地址开始，逐级向上回退
address_levels = ["北京市", "西城区", "广安门外大街", "广安门桥"]

for num_levels in range(len(address_levels), 0, -1):
    # 构建查询地址
    query = "".join(address_levels[:num_levels])
    # city 始终使用第一级（省/直辖市）
    city = address_levels[0]
    
    result = amap_search(query, city=city)
    if result and validate_result(result):
        break
```

### 3. 缓存污染

**问题描述**: 之前错误的查询结果被缓存，导致重复出现错误。

**解决方案**:

```python
def clean_cache_by_region(cache_file, valid_lat_range, valid_lon_range):
    """清除不在目标区域内的缓存条目"""
    with open(cache_file, 'r') as f:
        cache = json.load(f)
    
    cleaned = {}
    removed = 0
    
    for key, value in cache.items():
        lat, lon = value.get('latitude'), value.get('longitude')
        if lat and lon:
            if valid_lat_range[0] <= lat <= valid_lat_range[1] and \
               valid_lon_range[0] <= lon <= valid_lon_range[1]:
                cleaned[key] = value
            else:
                removed += 1
                print(f"Removed: {key} ({lat}, {lon})")
    
    print(f"Removed {removed} invalid entries")
    return cleaned
```

**上海地区示例**:
```python
# 上海坐标范围: 纬度 30-32°N, 经度 120-122°E
cleaned = clean_cache_by_region(
    "geocode_cache.json",
    valid_lat_range=(30, 32),
    valid_lon_range=(120, 122)
)
```

### 4. API 返回歧义结果

**问题描述**: API 返回的结果与查询地址的行政区不匹配。

**典型案例**:
```
查询: 浙江省-杭州市-上城区-孤山路25号-杭州博物馆
❌ 错误结果: (28.31, 120.79) - 永嘉县孤山中小学
✅ 正确位置: 杭州市上城区 (30.24, 120.16)
```

**解决方案**: 验证机制

```python
def validate_geocode_result(query_address, result):
    """验证地理编码结果"""
    # 验证1: 行政区一致性
    query_province = query_address.split('-')[0]
    if query_province not in result.get('formattedAddress', ''):
        return False
    
    # 验证2: 坐标距离合理性
    city_center = get_city_center(query_address)
    distance = haversine(
        city_center, 
        (result['latitude'], result['longitude'])
    )
    
    # 根据查询层级设置阈值
    max_distance = {
        'street': 20,   # km
        'district': 50,
        'city': 150,
        'province': 800
    }
    
    level = get_address_level(query_address)
    return distance <= max_distance.get(level, 100)
```

## 高德 API 最佳实践

### 参数配置

```python
params = {
    "key": AMAP_KEY,
    "keywords": query,
    "city": city,           # 使用省级或市级行政区
    "citylimit": "true",    # 限制搜索范围（关键！）
    "output": "JSON",
    "extensions": "all"     # 获取完整信息
}
```

### 推荐查询策略

1. **完整地址优先**: 从最完整的地址开始查询
2. **逐级回退**: 查询失败时，去掉最后一级再试
3. **验证结果**: 检查返回的行政区是否匹配
4. **缓存有效结果**: 只缓存通过验证的结果

## Nominatim 备选方案

当高德 API 无法准确定位时，可尝试 OSM Nominatim:

```python
def nominatim_search(query, country_code="cn"):
    """使用 Nominatim 搜索"""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "countrycodes": country_code,
        "limit": 1
    }
    headers = {"User-Agent": "GeoloreTool/1.0"}
    
    response = requests.get(url, params=params, headers=headers)
    time.sleep(1)  # 遵守 API 限制
    return response.json()
```

## 手动修复规则

对于 API 无法正确解析的地点，可以创建手动修复规则:

```python
# 手动修正规则: 地点名称 -> 精确查询词
FIX_RULES = {
    "复兴公园": "复兴公园 复兴中路 黄浦",
    "三官堂桥": "三官堂桥 普陀",
    "大都会舞厅": "大都会 南京西路 舞厅",
    # ...
}

def get_fixed_query(title):
    """获取修正后的查询词"""
    return FIX_RULES.get(title, title)
```

## 调试建议

1. **启用详细日志**: 使用 `--verbose` 参数查看每次查询的详情
2. **导出失败列表**: 记录所有解析失败或需要人工审核的地点
3. **批量验证**: 完成后批量检查坐标是否在预期区域内
4. **缓存审计**: 定期检查缓存中是否有异常数据
