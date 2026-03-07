# 自动下载脚本使用指南

## 📚 三种下载方式

### 1. 快速下载（推荐）
**最简单的方式，一键下载所有待下载书籍**

```bash
cd /Users/jrenc/Downloads/Jrenc_Current_Projects/Geolore/geolore_tools
./scripts/quick_download.sh
```

特点：
- ✅ 最简单，无需参数
- ✅ 自动下载队列中的前 25 本书
- ✅ 自动跳过已下载的书籍
- ✅ 显示实时配额信息

---

### 2. 智能循环下载
**持续下载直到配额用完或队列为空**

```bash
cd /Users/jrenc/Downloads/Jrenc_Current_Projects/Geolore/geolore_tools
./scripts/auto_download.sh
```

**高级用法：**

```bash
# 保留 5 次配额（不用完）
./scripts/auto_download.sh --min-quota 5

# 最多运行 3 轮
./scripts/auto_download.sh --max-rounds 3

# 每轮之间延迟 5 秒
./scripts/auto_download.sh --delay 5

# 组合使用
./scripts/auto_download.sh --min-quota 3 --max-rounds 5 --delay 2
```

特点：
- ✅ 自动循环下载，直到配额用完
- ✅ 可设置保留配额
- ✅ 可限制运行轮数
- ✅ 自动统计总下载数

---

### 3. Python 脚本（高级）
**完全可定制的下载脚本**

```bash
cd /Users/jrenc/Downloads/Jrenc_Current_Projects/Geolore/geolore_tools

# 基本用法
python scripts/auto_download_until_quota_exhausted.py

# 保留 5 次配额
python scripts/auto_download_until_quota_exhausted.py --min-quota 5

# 每批下载 10 本
python scripts/auto_download_until_quota_exhausted.py --batch-size 10

# 自定义输出目录
python scripts/auto_download_until_quota_exhausted.py --output-dir /path/to/books

# 每本书之间延迟 5 秒
python scripts/auto_download_until_quota_exhausted.py --delay 5
```

特点：
- ✅ 完全可定制
- ✅ 可指定输出目录
- ✅ 可调整批次大小
- ✅ 可设置下载延迟

---监控

所有脚本都会自动显示 API 配额信息：

```
📊 配额: 17/25 次/天
```

- **17** = 剩余可用次数
- **25** = 每天总配额
- 配额每天重置

---

## 🎯 使用建议

### 日常使用
```bash
# 最简单：直接运行快速下载
./scripts/quick_download.sh
```

### 批量下载
```bash
# 下载直到只剩 3 次配额
./scripts/auto_download.sh --min-quota 3
```

### 测试/调试
```bash
# 只运行 1 轮，看看效果
./scripts/auto_download.sh --max-rounds 1
```

---

## 📝 下载流程

1. **查看队列**
   ```bash
   ./geolore daily_book_harvest.py --show-queue
   ```

2. **开始下载**
   ```bash
   ./scripts/quick_download.sh
   ```

3. **查看结果**
   ```bash
   ls -lh output/books/
   ```

4. **处理书籍**（提取地理信息）
   ```bash
   GEOLORE_API_KEY=sk-YOWIYOnEr1m0LwfM7kODaQ8WPNiKIq60yKZY8IDbA4KWjQIr \
   python scripts/batch_process_all_books.py --book-concurrency 3
   ```

---

## ⚠️ 注意事项

1. **FlareSolverr 必须运行**
   ```bash
   docker ps | grep flaresolverr
   # 如果没有运行：
   docker start flaresolverr
   ```

2. **配额限制**
   - 每天 25 次下载配额
   - 配额用完后需等待第二天重置
   - 建议保留 2-3 次配额以备不时之需

3. **网络问题**
   - 如果连续失败，检查 FlareSolverr 日志
   - 可能需要重启 FlareSolverr：`docker restart flaresolverr`

4. **下载失败**
   - 某些书籍可能无法下载（如诗歌、乐谱等）
   - 失败的书籍会标记为 `failed` 状态
   - 可以手动从注册表中移除不合适的条目

---

## 🔧 故障排查

### 问题：FlareSolverr 报错
```bash
# 查看日志
docker logs --tail 50 flaresolverr

# 重启服务
docker restart flaresolverr
```

### 问题：下载的是乱码
- 已修复：代码会自动过滤乐谱、教材等不相关内容
- 已修复：安装了 pdfplumber 正确提取 PDF 文本
- 已修复：自动验证文本质量，丢弃乱码

### 问题：配额显示不准确
- 配额信息来自 Anna's Archive API
- 只有在实际调用 API 下载时才会更新
- 从缓存获取的书籍不消耗配额

---

## 📂 文件位置

- **下载脚本**：`geolore_tools/scripts/`
  - `quick_download.sh` - 快速下载
  - `auto_download.sh` - 智能循环下载
  - `auto_download_until_quota_exhausted.py` - Python 脚本

- **下载的书籍**：`geolore_tools/output/books/`
  - 每本书一个目录
  - 包含 `.txt` 文本文件和 `fetch_meta.json` 元数据

- **缓存**：`geolore_tools/output/.text_cache/`
  - 自动缓存已下载的书籍
  - 避免重复下载

---

## 🎉 快速开始

```bash
# 1. 确保 FlareSolverr 运行
docker start flaresolverr

# 2. 进入工具目录
cd /Users/jrenc/Downloads/Jrenc_Current_Projects/Geolore/geolore_tools

# 3. 运行快速下载
./scripts/quick_download.sh

# 完成！
```
