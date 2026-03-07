# AI文档索引

本目录包含所有面向AI的技术规范和协议文档。

---

## 🤖 文档列表

### 1. [ContentPackSpec.md](ContentPackSpec.md) - 内容包JSON协议 ⭐ 核心
**用途**：定义App可读取的内容包格式
**关键内容**：
- JSON Schema v2 定义
- 字段约束和验证规则
- 导入与幂等语义
- 时间序列支持（Timeline）
- 故事模式扩展（Story Mode）

**何时使用**：
- 生成内容包时（`build_pack.py`）
- 验证内容包格式时
- 实现新的导入功能时

---

### 2. [GeocodingRules.md](GeocodingRules.md) - 地理编码规则 ⭐ 核心
**用途**：定义地名→坐标转换的规则和验证机制
**关键内容**：
- 分级回退原则（从完整地址到省级）
- API调用策略（高德/Nominatim）
- 结果验证机制（行政区一致性、距离合理性）
- 防止歧义的关键点
- 完整解析流程（从数据到部署）

**何时使用**：
- 地理编码时（`geocode_places.py`）
- 验证坐标准确性时
- 修复错误坐标时

---

### 3. [PointSchema.md](PointSchema.md) - 地点数据Schema
**用途**：定义地点数据的结构和字段
**关键内容**：
- 地点对象字段定义
- 必填/可选字段说明
- 数据类型约束
- 示例数据

**何时使用**：
- 提取地点数据时（`auto_pipeline.py`）
- 验证数据格式时
- 设计新字段时

---

### 4. [TimelineSpec.md](TimelineSpec.md) - 时间序列规范
**用途**：定义时间序列内容包的特殊规范
**关键内容**：
- `orderIndex` 字段（必填）
- `dateStart`/`dateEnd` 字段（可选）
- 时间序列导航逻辑
- 人物传记 vs 小说情节的区别

**何时使用**：
- 生成传记类内容包时
- 生成小说情节地图时
- 实现时间线浏览功能时

---

### 5. [ValidationMechanism.md](ValidationMechanism.md) - 验证机制
**用途**：定义地理编码结果的验证规则
**关键内容**：
- 行政区一致性检查
- 坐标距离合理性检查
- 验证失败处理策略
- 城市中心点坐标表

**何时使用**：
- 地理编码后验证时
- 发现坐标异常时
- 添加新城市支持时

---

### 6. [CloudKitSchema.json](CloudKitSchema.json) - CloudKit数据模型
**用途**：定义iOS App的CloudKit数据库Schema
**关键内容**：
- 记录类型定义（Map/Place/MapPlace等）
- 字段类型和索引
- 关系定义

**何时使用**：
- 理解App数据模型时
- 设计内容包格式时
- 调试CloudKit同步问题时

---

## 🔧 使用场景映射

### 场景1：生成内容包
**涉及文档**：
1. [PointSchema.md](PointSchema.md) - 确保地点数据格式正确
2. [ContentPackSpec.md](ContentPackSpec.md) -议生成JSON
3. [TimelineSpec.md](TimelineSpec.md) - 如果是时间序列内容

**工具**：`build_pack.py`

---

### 场景2：地理编码
**涉及文档**：
1. [GeocodingRules.md](GeocodingRules.md) - 遵循编码规则
2. [ValidationMechanism.md](ValidationMechanism.md) - 验证结果

**工具**：`geocode_places.py`

---

### 场景3：数据提取
**涉及文档**：
1. [PointSchema.md](PointSchema.md) - 提取符合Schema的数据

**工具**：`auto_pipeline.py`

---

### 场景4：数据验证
**涉及文档**：
1. [ValidationMechanism.md](ValidationMechanism.md) - 验证坐标
2. [GeocodingRules.md](GeocodingRules.md) - 检查编码质量
3. [ContentPackSpec.md](ContentPackSpec.md) - 验证内容包格式

**工具**：各种验证脚本

---

## ⚠️ 重要原则

### 1. 强制性规范
所有AI文档中的规范都是**强制性**的，必须严格遵守：
- 数据格式必须符合Schema
- 验证规则必须全部通过
- 协议字段不可随意修改

### 2. 向后兼容
修改规范时必须考虑向后兼容：
- 新增字段应为可选
- 废弃字段应保留一段时间
- 版本号应递增

### 3. 验证优先
生成数据后必须验证：
- 格式验证（JSON Schema）
- 业务验证（坐标合理性）
- 完整性验证（引用完整）

---

## 📝 文档维护

### 更新时机
- 协议变更时（如新增字段）
- 发现规范漏洞时
- 验证规则调整时

### 更新原则
- 保持精确性（无歧义）
- 保持结构化（易解析）
- 保持完整性（有示例）

### 版本管理
- 重大变更：递增主版本号（v1 → v2）
- 小改进：递增次版本号（v2.0 → v2.1）
- 修复：递增修订号（v2.1.0 → v2.1.1）
