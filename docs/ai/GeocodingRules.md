# 地点解析规则（Geocoding Rules）

## 核心原则

**分级回退原则**：地点解析必须从最完整的地址开始，逐级向上回退，直到找到匹配结果或耗尽所有层级。

## 解析流程

### 1. 地址分级

对于形如 `北京市-西城区-广安门外大街-广安门桥` 的地址：

- **层级划分**：按 `-` 分隔符分割为多个层级
  ```
  Level 0: 北京市
  Level 1: 西城区  
  Level 2: 广安门外大街
  Level 3: 广安门桥
  ```

### 2. 查询顺序（从完整到简略）

**关键原则**：从最完整的地址开始查询，而不是从最具体的地名开始。

#### 正确的查询顺序：

1. **第一次尝试**：`北京市-西城区-广安门外大街-广安门桥`（完整地址，4级）
   - 如果找到 → 返回结果 ✓
   - 如果未找到 → 继续

2. **第二次尝试**：`北京市-西城区-广安门外大街`（省略最后一级，3级）
   - 如果找到 → 返回结果 ✓
   - 如果未找到 → 继续

3. **第三次尝试**：`北京市-西城区`（省略最后两级，2级）
   - 如果找到 → 返回结果 ✓
   - 如果未找到 → 继续

4. **第四次尝试**：`北京市`（仅保留省级，1级）
   - 如果找到 → 返回结果 ✓
   - 如果未找到 → 标记为无法解析

#### ❌ 错误的查询顺序（当前问题）：

```
1. 只查询 "广安门桥"，city="广安门外大街" ❌
   → 问题：city参数不是有效的行政区
   → 结果：可能匹配到错误的地点

2. 只查询 "广安门外大街"，city="西城区" ❌  
   → 问题：缺少上级行政区约束
   → 结果：可能有多个同名街道

3. 只查询 "西城区"，city="北京市" ✓
   → 这一步是正确的
```

### 3. API调用策略

#### 高德地图API (AMap)

对于每一次查询尝试：

```python
# 构建完整查询地址
query_address = "-".join(levels[:current_level + 1])

# 提取有效的city参数（省级或市级行政区）
# 优先使用第2级（市级），其次第1级（省级）
if len(levels) >= 2:
    city = levels[0] + "-" + levels[1]  # 例如："北京市-西城区"
elif len(levels) >= 1:
    city = levels[0]  # 例如："北京市"
else:
    city = None

# 调用API
amap_place_search(
    key=amap_key,
    keywords=query_address,
    city=city,
    citylimit=True  # 必须限制在指定城市内
)
```

#### OpenStreetMap Nominatim

```python
# 构建完整查询地址
query_address = " ".join(levels[:current_level + 1])

# 如果有上级行政区，使用viewbox约束
if current_level > 0:
    parent_query = " ".join(levels[:current_level])
    # 先查询父级区域获取bbox
    parent_result = nominatim_search(parent_query)
    if parent_result and parent_result.get('bbox'):
        # 在父级区域bbox内搜索
        nominatim_search_params(
            q=query_address,
            viewbox=parent_result['bbox'],
            bounded=True  # 必须限制在viewbox内
        )
```

### 4. 结果验证与合理性检查

**关键原则**：API返回的结果可能不准确，必须进行多维度验证，确保结果与查询意图一致。

#### 4.1 行政区一致性检查

验证返回结果的行政区信息是否与查询的行政区匹配：

```python
def validate_locality_match(query_levels: list, result: dict) -> bool:
    """
    检查返回结果的locality是否与查询的行政区一致
    
    Args:
        query_levels: 查询地址层级，如 ["浙江省", "杭州市", "上城区", "孤山路25号", "杭州博物馆"]
        result: API返回的结果，包含 locality, formattedAddress 等字段
    
    Returns:
        True 如果匹配，False 如果不匹配
    """
    result_locality = result.get("locality", "")
    result_formatted = result.get("formattedAddress", "")
    
    # 提取查询中的省市区信息
    query_province = query_levels[0] if len(query_levels) >= 1 else ""
    query_city = query_levels[1] if len(query_levels) >= 2 else ""
    query_district = query_levels[2] if len(query_levels) >= 3 else ""
    
    # 检查1：locality应该在查询的行政区范围内
    if result_locality:
        if query_district and query_district not in result_locality and query_district not in result_formatted:
            print(f"  ⚠️  locality不匹配: 查询={query_district}, 返回={result_locality}")
            return False
        if query_city and query_city not in result_formatted:
            print(f"  ⚠️  city不匹配: 查询={query_city}, 返回={result_formatted}")
            return False
    
    # 检查2：formattedAddress应该包含查询的上级行政区
    if result_formatted:
        # 移除"省/市/区"等后缀进行模糊匹配
        query_city_base = query_city.replace("市", "").replace("地区", "")
        result_formatted_normalized = result_formatted.replace("省", "").replace("市", "")
        
        if query_city_base and query_city_base not in result_formatted_normalized:
            print(f"  ⚠️  formattedAddress不包含查询城市: 查询={query_city}, 返回={result_formatted}")
            return False
    
    return True
```

**实际案例：**

❌ **错误案例1：杭州博物馆被定位到永嘉县**
```
查询: 浙江省-杭州市-上城区-孤山路25号-杭州博物馆
返回: {
  "latitude": 28.318616,
  "longitude": 120.793515,
  "locality": "永嘉县",           # ❌ 错误！应该是"上城区"
  "formattedAddress": "孤山中小学"  # ❌ 错误！不在杭州市
}
```
原因：高德API将"孤山路"误匹配为永嘉县的"孤山村"

❌ **错误案例2：猎雁林被定位到江西省**
```
查询: 福建省-南平市-建阳区-水吉镇-猎雁林
返回: {
  "latitude": 26.409067,
  "longitude": 114.58971,         # ❌ 经度114度，在江西省
  "formattedAddress": "雁林村"     # ❌ 名字相似但位置错误
}
```
原因：使用geocode模式时没有严格限制地理范围，匹配到江西省吉安市的"雁林村"

#### 4.2 坐标距离合理性检查

验证返回的坐标是否在合理的地理范围内：

```python
import math

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """计算两点间的球面距离（单位：公里）"""
    R = 6371  # 地球半径（公里）
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c

# 中国主要城市中心点坐标（用于参考）
CITY_CENTERS = {
    "北京市": (39.9042, 116.4074),
    "上海市": (31.2304, 121.4737),
    "杭州市": (30.2741, 120.1551),
    "南平市": (26.6417, 118.1780),
    "福州市": (26.0745, 119.2965),
    # ... 可扩展
}

# 合理距离阈值（单位：公里）
MAX_DISTANCE_FROM_CITY = {
    "province": 800,   # 省级：最大800公里
    "city": 150,       # 市级：最大150公里
    "district": 50,    # 区级：最大50公里
    "street": 20,      # 街道/镇级：最大20公里
}

def validate_coordinate_distance(query_levels: list, result: dict) -> bool:
    """
    检查返回坐标是否在合理距离范围内
    
    Args:
        query_levels: 查询地址层级
        result: API返回结果，包含 latitude, longitude
    
    Returns:
        True 如果距离合理，False 如果距离异常
    """
    result_lat = result.get("latitude")
    result_lon = result.get("longitude")
    
    if not result_lat or not result_lon:
        return True  # 无坐标信息，跳过检查
    
    # 获取查询的城市
    query_city = query_levels[1] if len(query_levels) >= 2 else None
    
    if not query_city or query_city not in CITY_CENTERS:
        return True  # 无参考坐标，跳过检查
    
    city_lat, city_lon = CITY_CENTERS[query_city]
    distance = haversine_distance(city_lat, city_lon, result_lat, result_lon)
    
    # 根据查询层级确定合理距离阈值
    if len(query_levels) >= 4:
        max_distance = MAX_DISTANCE_FROM_CITY["street"]
    elif len(query_levels) >= 3:
        max_distance = MAX_DISTANCE_FROM_CITY["district"]
    elif len(query_levels) >= 2:
        max_distance = MAX_DISTANCE_FROM_CITY["city"]
    else:
        max_distance = MAX_DISTANCE_FROM_CITY["province"]
    
    if distance > max_distance:
        print(f"  ⚠️  距离异常: {query_city}中心 → 结果坐标 = {distance:.1f}km (阈值: {max_distance}km)")
        print(f"      查询坐标: ({city_lat}, {city_lon})")
        print(f"      返回坐标: ({result_lat}, {result_lon})")
        return False
    
    return True
```

**实际案例：**

```python
# 杭州博物馆案例
query = ["浙江省", "杭州市", "上城区", "孤山路25号", "杭州博物馆"]
result = {
    "latitude": 28.318616,   # 实际在温州永嘉县
    "longitude": 120.793515
}

# 杭州市中心: (30.2741, 120.1551)
# 距离计算: haversine((30.2741, 120.1551), (28.318616, 120.793515))
# 结果: ≈ 225 公里 ❌ 超过阈值50公里

validate_coordinate_distance(query, result)  # 返回 False
```

#### 4.3 综合验证流程

将所有验证步骤整合到地点解析流程中：

```python
def geocode_with_validation(address: str, levels: list) -> dict:
    """
    带验证的地点解析流程
    
    Args:
        address: 完整地址字符串
        levels: 地址层级列表
    
    Returns:
        验证通过的地理编码结果，或 None
    """
    # 逐级回退查询
    for i in range(len(levels), 0, -1):
        query_levels = levels[:i]
        query_str = " ".join(query_levels)
        
        # 调用API
        result = amap_place_search(
            keywords=query_str,
            city=levels[0],  # 使用省级作为city参数
            citylimit=True
        )
        
        if not result:
            continue  # 未找到，继续回退
        
        # === 验证阶段 ===
        
        # 验证1：行政区一致性
        if not validate_locality_match(query_levels, result):
            print(f"  ❌ 验证失败: 行政区不匹配，继续回退...")
            continue
        
        # 验证2：坐标距离合理性
        if not validate_coordinate_distance(query_levels, result):
            print(f"  ❌ 验证失败: 坐标距离异常，继续回退...")
            continue
        
        # 验证3：地名相似度检查（可选）
        if len(query_levels) >= 2:
            query_poi = query_levels[-1]
            result_name = result.get("name", "")
            if query_poi and result_name and query_poi not in result_name:
                # 如果POI名称完全不匹配，发出警告但不拒绝
                print(f"  ⚠️  地名不完全匹配: 查询={query_poi}, 返回={result_name}")
        
        # === 验证通过 ===
        print(f"  ✅ 验证通过: 层级{i}, 匹配方法={result.get('matchMethod')}")
        result["matchLevel"] = len(levels) - i  # 记录回退层级
        result["validationPassed"] = True
        return result
    
    # 所有层级都验证失败
    print(f"  ❌ 无法找到有效结果")
    return None
```

#### 4.4 验证失败后的处理策略

当验证失败时，有以下几种处理策略：

1. **继续回退到上一级地址**：最常用的策略
2. **尝试替代API**：如果高德API失败，尝试Nominatim
3. **人工审核标记**：将验证失败的地点标记为需要人工审核
4. **使用上级行政区坐标**：如果所有尝试都失败，使用区县或城市的中心点坐标

```python
# 策略示例
def geocode_with_fallback(address: str, levels: list) -> dict:
    # 策略1: 高德API + 验证
    result = geocode_with_validation(address, levels)
    if result and result.get("validationPassed"):
        return result
    
    # 策略2: 尝试Nominatim API
    result = nominatim_geocode_with_validation(address, levels)
    if result and result.get("validationPassed"):
        return result
    
    # 策略3: 使用上级行政区中心点
    if len(levels) >= 2:
        city = levels[1]
        if city in CITY_CENTERS:
            lat, lon = CITY_CENTERS[city]
            return {
                "latitude": lat,
                "longitude": lon,
                "formattedAddress": f"{levels[0]}{city}",
                "geocodeSource": "fallback_city_center",
                "matchLevel": len(levels) - 2,
                "validationPassed": False,
                "needsManualReview": True
            }
    
    return None  # 完全失败
```

### 5. 防止歧义的关键点

#### 问题案例：通州的歧义

- **北京市-通州区** vs **江苏省-南通市-通州区**
- 如果只查询"通州"，可能匹配到错误的地点

#### 解决方法：

1. **始终使用完整地址**：`北京市-通州区` 而不是 `通州区`
2. **设置city参数**：明确指定 `city="北京市"`
3. **启用citylimit**：`citylimit=True` 强制限制搜索范围
4. **使用viewbox/bbox**：在父级行政区的地理范围内搜索
5. **应用第4节的验证机制**：即使API返回结果，也要验证其合理性

### 6. 缓存策略

为了提高效率和减少API调用：

1. **缓存完整地址**：缓存键应该包含完整的查询路径
   ```
   cache_key = "amap|geo|北京市-西城区|北京市-西城区-广安门外大街-广安门桥"
   ```

2. **缓存各级结果**：每个层级的查询结果都应该被缓存
   ```
   cache["北京市"] = {...}
   cache["北京市-西城区"] = {...}
   cache["北京市-西城区-广安门外大街"] = {...}
   cache["北京市-西城区-广安门外大街-广安门桥"] = {...}
   ```

3. **缓存失效策略**：
   - 成功结果：缓存30天
   - 失败结果（404）：缓存7天
   - 错误结果（5xx）：不缓存
   - **验证失败的结果**：不缓存，以便下次重新尝试

### 7. 元数据记录

对于每次解析，记录以下元数据：

```json
{
  "title": "广安门桥",
  "address": "北京市-西城区-广安门外大街-广安门桥",
  "latitude": 39.8948,
  "longitude": 116.3543,
  "formattedAddress": "北京市西城区广安门外大街广安门桥",
  
  // 解析元数据
  "geocodeSource": "amap",
  "matchLevel": 0,  // 0=完整匹配, 1=回退1级, 2=回退2级...
  "matchMethod": "amap_scoped_exact",
  "matchedQuery": "北京市-西城区-广安门外大街-广安门桥",
  "geocodeFirstAttempt": "hit",
  "geocodeNote": "first_hit",
  
  // 新增：验证元数据
  "validationPassed": true,
  "validationChecks": {
    "localityMatch": true,
    "distanceCheck": true,
    "distanceFromCityCenter": 8.5  // 单位：公里
  }
}
```

## 实施检查清单

在实施地点解析功能时，必须确保：

**基础查询：**
- [ ] 从完整地址开始查询，而不是从最后一级开始
- [ ] 逐级回退时保持上级行政区的约束
- [ ] 使用有效的city参数（省级或市级行政区）
- [ ] 启用地理范围限制（citylimit/bounded/viewbox）

**结果验证（重要）：**
- [ ] ✅ **验证返回结果的locality是否与查询行政区一致**
- [ ] ✅ **验证返回坐标是否在合理距离范围内**
- [ ] ✅ **验证失败时继续回退到上一级地址**
- [ ] 记录验证状态和详细元数据

**数据管理：**
- [ ] 缓存各级查询结果（但不缓存验证失败的结果）
- [ ] 记录匹配层级元数据
- [ ] 标记需要人工审核的地点

**特殊情况处理：**
- [ ] 处理同名地点的歧义（如"通州"）
- [ ] 处理地名相似但位置不同的情况（如"猎雁林"vs"雁林村"）
- [ ] 处理多音字和别名

## 错误案例总结与修正

### ❌ 错误做法1：查询策略错误

```python
# 只查询最后一级，使用上一级作为city
query = "广安门桥"
city = "广安门外大街"  # 街道名，不是有效的city参数
amap_place_search(keywords=query, city=city, citylimit=True)
# 结果：可能返回错误的地点
```

### ❌ 错误做法2：缺少结果验证

```python
# 没有验证就直接使用结果
    result = amap_place_search(keywords=query, city=city, citylimit=True)
    if result:
    return result  # ❌ 可能是错误的匹配！
```

**实际问题案例：**
- 查询"杭州博物馆"，返回"永嘉县孤山中小学"
- 查询"猎雁林（福建南平）"，返回"雁林村（江西吉安）"

### ✅ 正确做法：完整的验证流程

```python
def geocode_address_correctly(address: str) -> dict:
    """
    正确的地点解析流程（带验证）
    """
    # 1. 解析地址层级
    levels = address.split("-")  # 如: ["浙江省", "杭州市", "上城区", "孤山路25号", "杭州博物馆"]
    
    # 2. 逐级回退查询
    for i in range(len(levels), 0, -1):
        query_levels = levels[:i]
        query_str = " ".join(query_levels)
        
        # 3. 调用API（使用合理的city参数）
        city = levels[0] if len(levels) >= 1 else None
        result = amap_place_search(
            keywords=query_str,
            city=city,
            citylimit=True
        )
        
        if not result:
            continue  # 未找到，继续回退
        
        # 4. 验证阶段（关键！）
        
        # 4.1 行政区验证
        if not validate_locality_match(query_levels, result):
            print(f"❌ 行政区不匹配，继续回退...")
            continue
        
        # 4.2 距离验证
        if not validate_coordinate_distance(query_levels, result):
            print(f"❌ 坐标距离异常，继续回退...")
            continue
        
        # 5. 验证通过，返回结果
        result["matchLevel"] = len(levels) - i
        result["validationPassed"] = True
        return result
    
    # 6. 所有尝试都失败
return None

# 使用示例
result = geocode_address_correctly("浙江省-杭州市-上城区-孤山路25号-杭州博物馆")
if result and result.get("validationPassed"):
    print(f"✅ 成功: {result['formattedAddress']}")
    print(f"   坐标: ({result['latitude']}, {result['longitude']})")
else:
    print("❌ 无法找到有效结果")
```

### 实际修复案例

#### 案例1：杭州博物馆

```python
# 错误结果（未验证）：
{
  "latitude": 28.318616,
  "longitude": 120.793515,
  "locality": "永嘉县",
  "formattedAddress": "孤山中小学"
}

# 验证检查：
validate_locality_match(["浙江省", "杭州市", "上城区", ...], result)
# → 返回 False（永嘉县 ≠ 杭州市上城区）

validate_coordinate_distance([...], result)
# → 返回 False（距离杭州市中心225公里，超过阈值50公里）

# 结果：拒绝此结果，继续回退到"浙江省-杭州市-上城区"查询
```

#### 案例2：猎雁林

```python
# 错误结果（未验证）：
{
  "latitude": 26.409067,
  "longitude": 114.58971,
  "formattedAddress": "雁林村"  # 江西省吉安市
}

# 验证检查：
validate_coordinate_distance(["福建省", "南平市", "建阳区", ...], result)
# → 返回 False（经度114度，不在福建省范围118度附近）

# 正确结果（验证通过）：
{
  "latitude": 27.413183,
  "longitude": 118.347338,
  "formattedAddress": "福建省南平市建阳区水吉镇",
  "validationPassed": true
}
```

## 参考文档

- 高德地图API文档：https://lbs.amap.com/api/webservice/guide/api/search
- OpenStreetMap Nominatim文档：https://nominatim.org/release-docs/latest/api/Search/

---

## 总结

地点解析的核心要点：

1. **查询策略**：从完整地址开始，逐级回退
2. **地理约束**：使用city参数和citylimit限制搜索范围
3. **结果验证**：检查行政区一致性和坐标距离合理性（最重要！）
4. **失败处理**：验证失败时继续回退，而不是接受错误结果
5. **元数据记录**：记录验证状态和匹配层级

**验证机制可以有效防止：**
- 同名地点的误匹配（如"通州"）
- 相似地名的混淆（如"猎雁林"vs"雁林村"）
- 地名部分匹配的错误（如"孤山路"→"孤山村"）

---

**最后更新时间**：2025-11-17  
**版本**：v2.0（新增结果验证机制）  
**适用范围**：所有使用地理编码的功能模块

---

## 8. 完整解析流程（从数据到部署）

本节介绍从原始地点数据到最终部署到应用的完整操作流程。

### 8.1 流程概览

```
原始地点数据
    ↓
[1. 数据准备] 
    ↓
cleaned_places.filtered.json
    ↓
[2. 地点解析（带验证）]
    ↓
cleaned_places.filtered.geocoded.amap.json
    ↓
[3. 结果检查与修正]
    ↓
[4. 生成内容包]
    ↓
beipai-pack.v5.json
    ↓
[5. 部署到应用]
    ↓
geolore/Resources/beipai-pack.from-amap.json
    ↓
[6. 清理旧数据]
```

### 8.2 详细操作步骤

#### 步骤1：数据准备

**输入要求：**
```json
[
  {
    "title": "杭州博物馆",
    "address": "浙江省-杭州市-上城区-孤山路25号-杭州博物馆",
    "synopsis": "战国水晶杯是杭州博物馆的镇馆之宝...",
    "source": {...}
  },
  ...
]
```

**文件位置：**
```bash
# 北派盗墓笔记项目
北派盗墓笔记/03_AI汇总/cleaned_places.filtered.json

# 繁花项目
繁花/03_AI汇总/cleaned_places.filtered.shanghai.json
```

**数据格式要求：**
- 必须字段：`title`, `address`, `synopsis`
- `address` 格式：`省-市-区-街道-具体地点`（用 `-` 分隔）
- 编码：UTF-8
- 格式：JSON数组

#### 步骤2：运行地点解析脚本（带验证）

**2.1 基本用法**

```bash
cd 北派盗墓笔记/04_地点解析

# 设置高德API Key
export AMAP_KEY="你的高德API密钥"

# 运行解析脚本
python3 scripts/geocode_cleaned_places.py \
  --input ../03_AI汇总/cleaned_places.filtered.json \
  --output cleaned_places.filtered.geocoded.amap.json \
  --cache /tmp/geocode_cache.json \
  --provider amap \
  --amap-key "$AMAP_KEY" \
  --enable-validation \
  --verbose \
  --rps 10 \
  --concurrency 4 \
  --log logs/geocode_run.log
```

**2.2 参数说明**

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--input` | 输入文件路径 | 必填 |
| `--output` | 输出文件路径 | 必填 |
| `--provider` | API提供商（amap/nominatim） | `amap` |
| `--amap-key` | 高德API密钥 | 从环境变量读取 |
| `--enable-validation` | 启用结果验证（推荐） | `True` |
| `--disable-validation` | 禁用验证（不推荐） | `False` |
| `--rps` | 每秒请求数（Rate Limit） | `10` |
| `--concurrency` | 并发数 | `4` |
| `--cache` | 缓存文件路径 | `/tmp/geocode_cache.json` |
| `--verbose` | 显示详细日志 | `False` |
| `--log` | 日志文件路径 | 无（仅控制台输出） |

**2.3 验证模式说明**

启用验证（`--enable-validation`）后，脚本会对每个API返回的结果进行双重验证：

1. **行政区一致性检查**：验证返回的locality是否与查询的行政区匹配
2. **坐标距离合理性检查**：验证返回的坐标是否在合理距离范围内

只有通过**所有**验证检查的结果才会被采纳，否则会自动回退到上一级地址重试。

**2.4 监控解析进度**

```bash
# 查看实时日志
tail -f logs/geocode_run.log

# 查看已处理的地点数量
grep "处理进度" logs/geocode_run.log | tail -1

# 查看验证失败的案例
grep "❌ 验证失败" logs/geocode_run.log
```

**2.5 处理速度估算**

- **总地点数**：942个（北派盗墓笔记）
- **API速率限制**：10 RPS（每秒10次请求）
- **缓存命中率**：首次运行0%，重复运行>80%
- **预计耗时**：
  - 首次运行：约10-15分钟（每个地点可能需要多次回退查询）
  - 增量运行：约2-3分钟（大部分命中缓存）

#### 步骤3：结果检查与修正

**3.1 查看解析统计报告**

```bash
cd 北派盗墓笔记/04_地点解析

# 生成统计报告
python3 << 'EOF'
import json
with open('cleaned_places.filtered.geocoded.amap.json', 'r', encoding='utf-8') as f:
    places = json.load(f)

total = len(places)
geocoded = sum(1 for p in places if p.get('latitude') and p.get('longitude'))
validated = sum(1 for p in places if p.get('validationPassed'))
failed = total - geocoded

print(f"总地点数: {total}")
print(f"成功解析: {geocoded} ({geocoded/total*100:.1f}%)")
print(f"验证通过: {validated} ({validated/total*100:.1f}%)")
print(f"解析失败: {failed} ({failed/total*100:.1f}%)")
print(f"\n验证通过率: {validated/geocoded*100:.1f}%" if geocoded > 0 else "N/A")
EOF
```

**3.2 导出需要人工审核的地点**

```bash
# 导出验证失败的地点
python3 << 'EOF'
import json
with open('cleaned_places.filtered.geocoded.amap.json', 'r', encoding='utf-8') as f:
    places = json.load(f)

# 筛选验证失败或解析失败的地点
failed = [p for p in places if not p.get('validationPassed', False)]

print(f"需要人工审核的地点: {len(failed)}")
for p in failed[:10]:  # 显示前10个
    print(f"  - {p['title']}: {p.get('address', 'N/A')}")
    
# 保存到文件
with open('reports/failed_validation.json', 'w', encoding='utf-8') as f:
    json.dump(failed, f, ensure_ascii=False, indent=2)
EOF
```

**3.3 常见问题排查**

| 问题 | 可能原因 | 解决方法 |
|------|----------|----------|
| 验证失败率过高（>20%） | 地址格式不规范 | 检查输入数据的address格式 |
| 解析速度很慢 | 缓存失效或API限流 | 检查--rps参数，降低并发数 |
| 大量"距离异常"错误 | CITY_CENTERS缺少城市 | 添加缺失城市的中心点坐标 |
| API调用失败 | API密钥无效或配额耗尽 | 检查AMAP_KEY，查看API配额 |

**3.4 手动修正错误地点（如需要）**

```bash
# 创建修正脚本
cat > fix_specific_place.py << 'EOF'
import json

# 读取数据
with open('cleaned_places.filtered.geocoded.amap.json', 'r', encoding='utf-8') as f:
    places = json.load(f)

# 修正特定地点
for place in places:
    if place['title'] == '杭州博物馆':
        place['latitude'] = 30.2527
        place['longitude'] = 120.1450
        place['formattedAddress'] = '浙江省杭州市上城区孤山路25号'
        place['locality'] = '上城区'
        place['validationPassed'] = True
        place['manuallyFixed'] = True
        print(f"✅ 已修正: {place['title']}")

# 保存
with open('cleaned_places.filtered.geocoded.amap.json', 'w', encoding='utf-8') as f:
    json.dump(places, f, ensure_ascii=False, indent=2)
EOF

python3 fix_specific_place.py
rm fix_specific_place.py
```

#### 步骤4：生成内容包

**4.1 运行构建脚本**

```bash
cd 北派盗墓笔记/05_内容包

python3 scripts/build_pack_from_candidates.py \
  --input ../04_地点解析/cleaned_places.filtered.geocoded.amap.json \
  --output beipai-pack.v5.json \
  --pack-id "beipai-notes" \
  --pack-title "北派盗墓笔记地图 v5" \
  --pack-version 5 \
  --map-id "beipai-map" \
  --map-title "北派盗墓笔记" \
  --tags "文学" "盗墓" "小说" "地图"
```

**4.2 验证内容包格式**

```bash
# 检查JSON格式
python3 << 'EOF'
import json
try:
    with open('beipai-pack.v5.json', 'r', encoding='utf-8') as f:
        pack = json.load(f)
    print("✅ JSON格式正确")
    print(f"   Pack ID: {pack['pack']['id']}")
    print(f"   Pack Version: {pack['pack']['version']}")
    print(f"   Schema Version: {pack['schemaVersion']}")
    print(f"   Places: {len(pack['places'])}")
    print(f"   Map Places: {len(pack['mapPlaces'])}")
    
    # 检查必需字段
    assert pack['schemaVersion'] == 1, "Schema version must be 1"
    assert 'pack' in pack and 'id' in pack['pack'], "Missing pack.id"
    assert 'map' in pack and 'title' in pack['map'], "Missing map.title"
    print("✅ 所有必需字段完整")
except Exception as e:
    print(f"❌ 验证失败: {e}")
EOF
```

**4.3 内容包文件结构**

```json
{
  "schemaVersion": 1,
  "pack": {
    "id": "beipai-notes",
    "title": "北派盗墓笔记地图 v5",
    "version": 5,
    "applyMode": "replace"
  },
  "map": {
    "id": "beipai-map",
    "title": "北派盗墓笔记"
  },
  "tags": ["文学", "盗墓", "小说", "地图"],
  "places": [
    {
      "clientId": "geocoded-abc123",
      "title": "杭州博物馆",
      "latitude": 30.2527,
      "longitude": 120.1450,
      "locality": "上城区",
      "countryCode": "CN",
      "formattedAddress": "浙江省杭州市上城区孤山路25号",
      "originalAddress": "浙江省-杭州市-上城区-孤山路25号-杭州博物馆",
      "synopsis": "战国水晶杯是杭州博物馆的镇馆之宝...",
      "validationPassed": true
    }
  ],
  "mapPlaces": [
    {
      "placeClientId": "geocoded-abc123",
      "customTitle": "杭州博物馆",
      "orderIndex": 1,
      "pinStyle": "poi",
      "note": "战国水晶杯是杭州博物馆的镇馆之宝..."
    }
  ],
  "stories": [
    {
      "clientId": "geocoded-abc123-story-0001",
      "placeClientId": "geocoded-abc123",
      "type": "x-story",
      "payload": {
        "synopsis": "战国水晶杯是杭州博物馆的镇馆之宝...",
        "source": {
          "geocodeSource": "amap",
          "matchedQuery": "浙江省 杭州市 上城区 孤山路25号 杭州博物馆"
        }
      }
    }
  ]
}
```

#### 步骤5：部署到应用

**5.1 复制到Resources目录**

```bash
# 回到项目根目录
cd ../../..  # 现在在 geolore/ 目录

# 创建备份（如果存在旧版本）
if [ -f geolore/Resources/beipai-pack.from-amap.json ]; then
  cp geolore/Resources/beipai-pack.from-amap.json \
     geolore/Resources/beipai-pack.from-amap.json.backup.$(date +%Y%m%d_%H%M%S)
  echo "✅ 已备份旧版本"
fi

# 复制新版本（注意文件名必须是 beipai-pack.from-amap.json）
cp 北派盗墓笔记/05_内容包/beipai-pack.v5.json \
   geolore/Resources/beipai-pack.from-amap.json

echo "✅ 已部署到: geolore/Resources/beipai-pack.from-amap.json"
```

**5.2 验证部署**

```bash
# 检查文件大小和格式
ls -lh geolore/Resources/*.json

# 验证JSON格式和内容
python3 << 'EOF'
import json
with open('geolore/Resources/beipai-pack.from-amap.json', 'r', encoding='utf-8') as f:
    pack = json.load(f)
print(f"✅ 部署成功")
print(f"   Pack: {pack['pack']['title']} v{pack['pack']['version']}")
print(f"   地点数: {len(pack['places'])}")
print(f"   地图标记: {len(pack['mapPlaces'])}")
print(f"   故事: {len(pack.get('stories', []))}")
EOF
```

**5.3 应用加载说明**

iOS应用会在以下两个位置查找内容包：

1. **自动加载**（应用启动时）：
   ```swift
   // geoloreApp.swift: importBundledPackIfNeeded()
   Bundle.main.url(forResource: "beipai-pack.from-amap", withExtension: "json")
   ```

2. **手动安装**（用户点击商店中的安装按钮）：
   ```swift
   // StoreScreen.swift: installBeipaiPack()
   Bundle.main.url(forResource: "beipai-pack.from-amap", withExtension: "json")
   ```

**重要**：文件名**必须**是 `beipai-pack.from-amap.json`，否则应用会提示"找不到北派盗墓笔记内容包"。

**5.4 在Xcode中运行应用**

```bash
# 打开项目
open geolore.xcodeproj

# 或者使用命令行构建（可选）
xcodebuild -project geolore.xcodeproj \
           -scheme geolore \
           -destination 'platform=iOS Simulator,name=iPhone 15 Pro' \
           build
```

在Xcode中：
1. 选择目标设备（模拟器或真机）
2. 点击 ▶️ 运行
3. 在应用中进入"商店"界面
4. 点击"安装北派盗墓笔记"按钮
5. 等待提示"北派盗墓笔记安装完成：新建地点 942 个..."

#### 步骤6：清理旧数据

**6.1 删除旧版本内容包**

```bash
cd geolore

# 删除旧版本（保留当前版本和最近一次备份）
rm -f 北派盗墓笔记/05_内容包/beipai-pack.v3.json
rm -f 北派盗墓笔记/05_内容包/beipai-pack.v4.json
rm -f 北派盗墓笔记/05_内容包/beipai-pack.from-amap.json

# 清理旧备份（保留最近3个）
cd geolore/Resources
ls -t beipai-pack.from-amap.json.backup.* | tail -n +4 | xargs rm -f
cd ../..

echo "✅ 已清理旧版本文件"
```

**6.2 清理临时文件和日志**

```bash
# 清理旧日志（保留最近的）
cd 北派盗墓笔记/04_地点解析/logs
ls -t *.log | tail -n +6 | xargs rm -f

# 清理测试文件
cd ..
rm -f test_validation.json
rm -f test_validation.sh

# 清理临时缓存（可选，会导致下次运行变慢）
# rm -f /tmp/geocode_cache.json

echo "✅ 已清理临时文件"
```

**6.3 压缩归档旧版本（可选）**

```bash
cd geolore

# 创建归档目录
mkdir -p archives/$(date +%Y%m)

# 压缩旧版本
tar -czf archives/$(date +%Y%m)/beipai-pack-v4-archive-$(date +%Y%m%d).tar.gz \
  北派盗墓笔记/05_内容包/beipai-pack.v4.json \
  北派盗墓笔记/04_地点解析/cleaned_places.filtered.geocoded.amap.json.backup

echo "✅ 已归档到 archives/$(date +%Y%m)/"
```

### 8.3 完整操作脚本（一键执行）

```bash
#!/bin/bash
# 文件名: deploy_content_pack.sh
# 用途: 一键完成地点解析到部署的完整流程

set -e  # 遇到错误立即退出

PROJECT_ROOT="/Users/jrenc/Downloads/JrencsProject/geolore"
WORK_DIR="$PROJECT_ROOT/北派盗墓笔记"
AMAP_KEY="${AMAP_KEY:-36579ed95ec58b2aedca3b5e59a633be}"

echo "🚀 开始执行完整部署流程..."
echo ""

# 步骤1: 检查输入文件
echo "📂 步骤1/6: 检查输入文件..."
INPUT_FILE="$WORK_DIR/03_AI汇总/cleaned_places.filtered.json"
if [ ! -f "$INPUT_FILE" ]; then
  echo "❌ 错误: 输入文件不存在: $INPUT_FILE"
  exit 1
fi
echo "✅ 输入文件存在: $(wc -l < "$INPUT_FILE") 行"
echo ""

# 步骤2: 运行地点解析
echo "🗺️  步骤2/6: 运行地点解析（带验证）..."
cd "$WORK_DIR/04_地点解析"
python3 scripts/geocode_cleaned_places.py \
  --input "$INPUT_FILE" \
  --output cleaned_places.filtered.geocoded.amap.json \
  --cache /tmp/geocode_beipai_cache.json \
  --provider amap \
  --amap-key "$AMAP_KEY" \
  --enable-validation \
  --verbose \
  --rps 10 \
  --concurrency 4 \
  --log logs/geocode_run_$(date +%Y%m%d_%H%M%S).log
echo "✅ 地点解析完成"
echo ""

# 步骤3: 检查解析结果
echo "📊 步骤3/6: 检查解析结果..."
python3 << 'EOF'
import json
with open('cleaned_places.filtered.geocoded.amap.json', 'r', encoding='utf-8') as f:
    places = json.load(f)
total = len(places)
geocoded = sum(1 for p in places if p.get('latitude'))
validated = sum(1 for p in places if p.get('validationPassed'))
print(f"总地点数: {total}")
print(f"成功解析: {geocoded} ({geocoded/total*100:.1f}%)")
print(f"验证通过: {validated} ({validated/total*100:.1f}%)")
if validated < geocoded * 0.8:
    print("⚠️  警告: 验证通过率较低，建议人工检查")
EOF
echo ""

# 步骤4: 生成内容包
echo "📦 步骤4/6: 生成内容包..."
cd "$WORK_DIR/05_内容包"
PACK_VERSION=$(date +%Y%m%d)
python3 scripts/build_pack_from_candidates.py \
  --input ../04_地点解析/cleaned_places.filtered.geocoded.amap.json \
  --output beipai-pack.v$PACK_VERSION.json \
  --pack-id "beipai-notes" \
  --pack-title "北派盗墓笔记地图 v$PACK_VERSION" \
  --pack-version "$PACK_VERSION" \
  --map-id "beipai-map" \
  --map-title "北派盗墓笔记" \
  --tags "文学" "盗墓" "小说" "地图"
echo "✅ 内容包已生成: beipai-pack.v$PACK_VERSION.json"
echo ""

# 步骤5: 部署到应用
echo "🚢 步骤5/6: 部署到应用..."
cd "$PROJECT_ROOT"
RESOURCE_FILE="geolore/Resources/beipai-pack.from-amap.json"
if [ -f "$RESOURCE_FILE" ]; then
  cp "$RESOURCE_FILE" "$RESOURCE_FILE.backup.$(date +%Y%m%d_%H%M%S)"
  echo "✅ 已备份旧版本"
fi
cp "$WORK_DIR/05_内容包/beipai-pack.v$PACK_VERSION.json" "$RESOURCE_FILE"
echo "✅ 已部署到: $RESOURCE_FILE"
echo ""

# 步骤6: 清理旧文件
echo "🧹 步骤6/6: 清理旧文件..."
# 删除3天前的备份
find geolore/Resources -name "beipai-pack.*.backup.*" -mtime +3 -delete
# 删除7天前的日志
find "$WORK_DIR/04_地点解析/logs" -name "*.log" -mtime +7 -delete
echo "✅ 清理完成"
echo ""

# 完成
echo "🎉 部署流程完成！"
echo ""
echo "📱 下一步操作："
echo "   1. 在 Xcode 中打开项目: open $PROJECT_ROOT/geolore.xcodeproj"
echo "   2. 选择目标设备并运行应用"
echo "   3. 在应用的「商店」界面点击「安装北派盗墓笔记」"
echo ""
echo "📚 相关文档："
echo "   - 地点解析规则: $PROJECT_ROOT/docs/geocoding-rules.md"
echo "   - 内容包规范: $PROJECT_ROOT/docs/ContentPackSpec.md"
```

**使用方法：**

```bash
# 1. 保存脚本
cd /Users/jrenc/Downloads/JrencsProject/geolore
cat > deploy_content_pack.sh << 'EOF'
[粘贴上面的脚本内容]
EOF

# 2. 添加执行权限
chmod +x deploy_content_pack.sh

# 3. 运行脚本
./deploy_content_pack.sh

# 或者指定自定义AMAP_KEY
AMAP_KEY="你的密钥" ./deploy_content_pack.sh
```

### 8.4 常见问题与解决方案

#### Q1: 应用提示"找不到北派盗墓笔记内容包"

**原因：** 文件名不正确  
**解决：** 确保文件名是 `beipai-pack.from-amap.json`（不是 `beipai-pack.json`）

```bash
cd geolore/Resources
mv beipai-pack.json beipai-pack.from-amap.json  # 如果文件名错误
```

#### Q2: 验证通过率很低（<80%）

**原因：** 输入数据质量问题或CITY_CENTERS缺少城市  
**解决：**
1. 检查输入数据的address格式是否规范
2. 查看日志中的"距离异常"错误，添加缺失城市到CITY_CENTERS

```bash
grep "距离异常" logs/geocode_run.log | head -20
```

#### Q3: 解析速度很慢

**原因：** API限流或并发数过高  
**解决：** 降低--rps和--concurrency参数

```bash
# 降低速率限制
--rps 5 --concurrency 2
```

#### Q4: 内容包太大（>10MB）

**原因：** 地点数量过多  
**解决：** 拆分为多个内容包，或压缩JSON

```bash
# 压缩JSON（移除空白）
python3 -m json.tool --compact beipai-pack.v5.json > beipai-pack.v5.min.json
```

#### Q5: 地点在地图上显示位置错误

**原因：** 验证机制未启用或城市中心点坐标不准确  
**解决：**
1. 确保使用 `--enable-validation` 参数
2. 更新 `CITY_CENTERS` 中该城市的坐标
3. 手动修正该地点的坐标（参见8.2.4节）

### 8.5 性能优化建议

#### 缓存策略

```bash
# 使用持久化缓存文件
--cache ~/.geocode_cache/beipai.json

# 定期清理过期缓存（30天）
find ~/.geocode_cache -name "*.json" -mtime +30 -delete
```

#### 并发调优

```bash
# 根据网络状况调整
# 网络良好：--rps 15 --concurrency 6
# 网络一般：--rps 10 --concurrency 4
# 网络较差：--rps 5 --concurrency 2
```

#### 分批处理

```bash
# 将大文件拆分为多个批次
split -l 100 cleaned_places.filtered.json batch_

# 分别处理每个批次
for batch in batch_*; do
  python3 scripts/geocode_cleaned_places.py \
    --input "$batch" \
    --output "${batch}.geocoded.json" \
    --enable-validation
done

# 合并结果
jq -s 'add' batch_*.geocoded.json > all_geocoded.json
```

### 8.6 测试与验证清单

部署前必须完成以下检查：

**数据完整性：**
- [ ] 输入文件格式正确（JSON数组）
- [ ] 所有地点都有`title`和`address`字段
- [ ] `address`格式符合规范（省-市-区-街道-地点）

**解析质量：**
- [ ] 解析成功率 ≥ 95%
- [ ] 验证通过率 ≥ 80%
- [ ] 无明显的跨省/跨市错误

**内容包格式：**
- [ ] JSON格式正确（可解析）
- [ ] `schemaVersion` = 1
- [ ] `pack.id`和`pack.version`正确
- [ ] `places`和`mapPlaces`数量一致

**部署检查：**
- [ ] 文件名正确：`beipai-pack.from-amap.json`
- [ ] 文件位置正确：`geolore/Resources/`
- [ ] 文件大小合理（<10MB）
- [ ] 已备份旧版本

**应用测试：**
- [ ] 应用可以启动
- [ ] 可以在"商店"中看到内容包
- [ ] 点击安装后提示成功
- [ ] 地图上可以看到地点标记
- [ ] 点击标记可以查看详情

---

**流程版本**：v1.0  
**适用项目**：北派盗墓笔记、繁花（及其他类似项目）  
**最后更新**：2025-11-17

