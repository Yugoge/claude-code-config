# 图片提取增强计划 - 修复Bug + 添加小红书Fallback

## Context

### 问题背景
用户执行了图片重新提取（commit `5f6619b`）后，发现主计划（china-feb-15-mar-7）的图片来源统计为：
- Gaode: 134 (97%)
- Google: 1 (3%) ← **异常：所有POI都在中国，不应该有Google**

用户要求：
1. 重新提取重庆开始的计划的所有图片
2. 找出3% Google来源的根本原因

### 调查发现

#### 发现1：Orange Hotel Bug（真正的Bug）
- **问题POI**: Orange Hotel Beijing Zhongguancun Xueyuanqiao（Day 8）
- **错误表现**: 使用Google服务获取图片，应该用Gaode
- **根本原因**: Day 8的location字段是`"Shanghai / Beijing"`（transition day多城市字符串）
- **Bug流程**:
  ```
  POI extraction时，poi["city"] = day["location"] = "Shanghai / Beijing"
    ↓
  _map_service_for("Shanghai / Beijing") 找不到这个"城市"
    ↓
  _resolve_city_coord() 返回 (0, 0)
    ↓
  错误fallback到Google服务
  ```
- **为什么没用POI自己的coordinates**: `_map_service_for()`只接收city字符串，不接收POI的coordinates字段

#### 发现2：缺失用户的第3条设计规则
用户设计要求：高德/谷歌搜索失败 → 使用小红书搜索
当前代码：缺少小红书fallback实现

#### 发现3：Bucket-list的混合使用是正常fallback
- china-exchange-bucket-list: Gaode 87 + Google 77
- 原因：部分POI无coordinates字段 → 无法判断国家 → 合理fallback到Google
- **这不是bug**，而是正常的降级行为

### 修复目标
1. **修复Orange Hotel bug**：支持POI自己的coordinates，不依赖多城市location字符串
2. **实现小红书fallback**：补齐用户的第3条设计规则
3. **改进无坐标处理**（可选）：添加中国城市列表fallback，减少不必要的Google使用
4. **验证修复效果**：主计划应该100% Gaode（当前97%）

---

## 用户的设计

### 规则1: 服务选择（基于geopip）
```
中国 (ISO2=CN) → 高德
非中国 → 谷歌
```

### 规则2: 搜索方式
```
全部使用关键词搜索（不用坐标搜索）
```

### 规则3: Fallback策略
```
高德/谷歌搜索失败 → 小红书搜索
```

---

## 当前状态分析

### ✅ 已正确实现

1. **服务选择逻辑** (`_map_service_for()` lines 148-169)
   - 使用geopip检测坐标 → ISO2
   - CN → 高德，非CN → 谷歌
   - 有缓存机制
   - **工作正常**：主计划97% Gaode + 3% Google

2. **关键词搜索** (lines 356-468)
   - Gaode：100%使用keyword search
   - Google：100%使用文本查询
   - **没有坐标搜索代码**

3. **基础Fallback** (lines 369-392)
   - Gaode内部有搜索策略fallback
   - 原始名称 → 简化名称 → 地址搜索

### ❌ 缺失功能

**小红书Fallback** - 核心缺陷
- 高德/谷歌失败后没有任何外部fallback
- 小红书skill存在且可用但未集成

---

## "中国POI用Google"问题的真相

### 问题表现
从commit `5f6619b` 的数据：
```
china-feb-15-mar-7 (主计划):
  Gaode: 134 (97% 中文键)
  Google: 1 (3% 英文键)
  状态: ✅ 几乎完美

china-exchange-bucket-list:
  Gaode: 87 (100% 中文键)
  Google: 77 (100% 英文键)
  状态: ⚠️ 混合使用
```

### 根本原因 #1: Bucket-list正常Fallback

**这不是bug，是正常的fallback行为**：

```python
# lines 162-165
lng, lat = self._resolve_city_coord(city)
if lng == 0.0 and lat == 0.0:
    return "google"  # 无坐标时默认Google
```

**逻辑链**：
```
Bucket-list某些城市POI无coordinates字段
    ↓
_resolve_city_coord() 找不到坐标 → 返回(0, 0)
    ↓
_map_service_for() 判断为"未知国家" → 默认Google
    ↓
使用Google搜索（因为无法确定是否在中国）
```

### 根本原因 #2: ⚠️ Orange Hotel Bug - 多城市Location字段

**这是一个真正的BUG！**

**问题POI**：
- Name: Orange Hotel Beijing Zhongguancun Xueyuanqiao
- Day: 8 (Day 8 location: "Shanghai / Beijing" - transition day)
- POI coordinates: `{lat: 39.989405, lng: 116.345394}` ← 正确的北京坐标
- image_url: Google来源 ← **错误！应该用Gaode**

**Bug流程**：
```
accommodation.json Day 8:
  location: "Shanghai / Beijing"  ← 多城市transition day
  accommodation.coordinates: {北京坐标}  ← POI自己的坐标（正确）
    ↓
fetch-images-batch.py line 666:
  poi["city"] = location  ← 继承day的location字段
  poi["city"] = "Shanghai / Beijing"  ← 伪城市名
    ↓
_map_service_for("Shanghai / Beijing"):
  _resolve_city_coord("Shanghai / Beijing") → 找不到这个"城市" → (0, 0)
    ↓
  判断为未知国家 → return "google"
    ↓
  ❌ 错误使用Google服务获取北京酒店图片
```

**为什么没用POI自己的coordinates**：
- `_map_service_for()` 只接收 `city` 字符串参数
- 不接收POI的coordinates字段
- 即使POI有正确的北京坐标，也无法使用

**为什么主计划其他POI正常**：
- 其他天的location都是单城市（"Chongqing", "Beijing"等）
- `_resolve_city_coord()` 能找到这些城市的坐标
- geopip正确识别 → 使用Gaode
- **只有Day 8是transition day，location="Shanghai / Beijing"导致异常**

**为什么bucket-list混合**：
- 部分POI无coordinates → 无法确定国家 → 默认Google（正常fallback）
- 有coordinates的POI → geopip识别 → 正确使用Gaode
- **这是合理的降级行为**（与Orange Hotel bug不同）

---

## 实施方案

### Phase 0: 修复多城市Location Bug (Orange Hotel问题)

#### 问题：
POI extraction时，`poi["city"]` 直接继承day的`location`字段。当location是多城市字符串（如"Shanghai / Beijing"）时，`_map_service_for()`无法识别，错误fallback到Google。

#### 解决方案1：优先使用POI自己的coordinates

**修改 `_map_service_for()` 函数签名和逻辑** (lines 148-169):

```python
def _map_service_for(self, city: str, poi_coordinates: dict = None) -> str:
    """Return 'gaode' or 'google' based on coordinate-level country detection.

    Args:
        city: City name (may be multi-city like "Shanghai / Beijing")
        poi_coordinates: Optional POI's own coordinates dict with 'lat' and 'lng'
                        If provided, will use these instead of city-level coordinates

    Universal rule — no config, no hardcoded city lists:
      Mainland China (ISO2=CN) → Gaode (高德)
      Everywhere else (HK, MO, TW, JP, FR, ...) → Google

    Detection: coordinate (POI or city) → geopip → ISO2.
    Results cached per city per session.
    """
    # If POI has its own coordinates, use them directly
    if poi_coordinates and 'lat' in poi_coordinates and 'lng' in poi_coordinates:
        lng = poi_coordinates['lng']
        lat = poi_coordinates['lat']
        if lng != 0.0 and lat != 0.0:
            iso2 = self._country_for_coord(lng, lat)
            return "gaode" if iso2 == "CN" else "google"

    # Fall back to city-based detection
    cache_key = city.strip().lower()
    if cache_key in self._country_cache:
        return "gaode" if self._country_cache[cache_key] == "CN" else "google"

    lng, lat = self._resolve_city_coord(city)
    if lng == 0.0 and lat == 0.0:
        self._country_cache[cache_key] = ""
        return "google"

    iso2 = self._country_for_coord(lng, lat)
    self._country_cache[cache_key] = iso2
    return "gaode" if iso2 == "CN" else "google"
```

#### 解决方案2：传递POI coordinates到所有调用点

**修改 POI extraction** (lines 660-670):
```python
# 添加coordinates字段到POI dict
if name_base:
    poi_dict = {
        "name_base": name_base,
        "name_local": name_local,
        "city": location,
        "location_base": location_base,
        "location_local": location_local,
        "type": poi_type
    }

    # 添加POI自己的coordinates（如果有）
    if field_name == "accommodation":
        acc_coords = day_data.get("accommodation", {}).get("coordinates")
        if acc_coords:
            poi_dict["coordinates"] = acc_coords
    # meals/attractions等也可能有coordinates，按需添加

    pois.append(poi_dict)
```

**修改 fetch_poi_photos调用** (line 903):
```python
service = self._map_service_for(poi['city'], poi.get('coordinates'))
```

**修改 fetch_poi_photo调用** (line 923-927):
```python
photo_url = self.fetch_poi_photo(
    poi['name_base'],
    poi['city'],
    name_local=poi.get('name_local'),
    location_local=poi.get('location_local'),
    poi_coordinates=poi.get('coordinates')  # 新增参数
)
```

**修改 fetch_poi_photo函数签名** (line 450):
```python
def fetch_poi_photo(self, poi_name: str, city: str, name_local: str = None,
                   location_local: str = None, poi_coordinates: dict = None) -> Optional[str]:
    """Fetch POI photo using map service determined by city location or POI coordinates.

    Args:
        poi_name: POI name (English)
        city: City name (may be multi-city)
        name_local: Local language POI name
        location_local: Local language location/address
        poi_coordinates: POI's own coordinates (overrides city-based detection)
    """
    search_name = name_local if name_local else poi_name
    service = self._map_service_for(city, poi_coordinates)

    # ... rest of function
```

#### 效果：
- Orange Hotel有北京坐标 → 直接用坐标判断 → ISO2=CN → Gaode ✓
- 即使city="Shanghai / Beijing"，也能正确选择服务
- 不影响现有逻辑（coordinates=None时仍然用city判断）

---

### Phase 1: 添加小红书Fallback

#### 文件: `scripts/fetch-images-batch.py`

#### 修改1: 新增小红书搜索方法

**位置**: 新增函数（在line 468后）

```python
def _xiaohongshu_search(self, search_name: str, city: str) -> str:
    """
    小红书搜索fallback

    当高德/谷歌搜索失败时使用

    Args:
        search_name: POI名称（中文优先）
        city: 城市名称

    Returns:
        图片URL或None
    """
    try:
        import subprocess

        # 构建搜索关键词
        search_query = f"{city} {search_name}"

        # 调用小红书search skill
        script_path = self.base_dir / ".claude/skills/rednote/scripts/search.py"

        if not script_path.exists():
            logger.warning(f"Xiaohongshu skill not found at {script_path}")
            return None

        result = subprocess.run(
            [self.venv_python, str(script_path), search_query, "--limit", "5"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            logger.error(f"Xiaohongshu search failed: {result.stderr}")
            return None

        # 解析结果
        data = json.loads(result.stdout)

        if data.get("status") != "success":
            return None

        notes = data.get("data", [])
        if not notes:
            return None

        # 从第一条笔记中提取图片
        first_note = notes[0]
        images = first_note.get("images", [])

        if images and len(images) > 0:
            # 返回第一张图片URL
            return images[0]

        return None

    except subprocess.TimeoutExpired:
        logger.error("Xiaohongshu search timeout")
        return None
    except Exception as e:
        logger.error(f"Xiaohongshu search error: {e}")
        return None
```

#### 修改2: 更新fetch_poi_photo支持小红书fallback

**位置**: Lines 450-468

**修改前**:
```python
def fetch_poi_photo(self, poi_name: str, city: str, name_local: str = None, location_local: str = None):
    search_name = name_local if name_local else poi_name
    service = self._map_service_for(city)

    if service == "gaode":
        search_with_city = f"{city}{search_name}"
        return self._gaode_search(search_with_city, city, location_local=location_local)
    else:
        return self.fetch_poi_photo_google(search_name, city)
```

**修改后**:
```python
def fetch_poi_photo(self, poi_name: str, city: str, name_local: str = None, location_local: str = None):
    """
    获取POI照片，支持多层fallback

    Fallback链:
    1. 高德/谷歌（根据geopip判断）
    2. 小红书搜索
    """
    search_name = name_local if name_local else poi_name
    service = self._map_service_for(city)

    # 第一层：高德/谷歌搜索
    photo_url = None
    if service == "gaode":
        search_with_city = f"{city}{search_name}"
        photo_url = self._gaode_search(search_with_city, city, location_local=location_local)
    else:
        photo_url = self.fetch_poi_photo_google(search_name, city)

    # 如果第一层成功，直接返回
    if photo_url:
        return photo_url

    # 第二层：小红书fallback
    logger.info(f"Primary search failed for {poi_name}, trying Xiaohongshu")
    photo_url = self._xiaohongshu_search(search_name, city)

    if photo_url:
        logger.info(f"Found photo from Xiaohongshu for {poi_name}")
        return photo_url

    # 所有fallback都失败
    return None
```

#### 修改3: 更新fetch输出以显示来源

**位置**: Lines 923-937

**修改前**:
```python
photo_url = self.fetch_poi_photo(poi['name_base'], poi['city'], poi.get('name_local'), poi.get('location_local'))
if photo_url:
    self.cache["pois"][cache_key] = photo_url
    self._save_cache()
    print("✓")
else:
    print("✗")
```

**修改后**:
```python
photo_url = self.fetch_poi_photo(poi['name_base'], poi['city'], poi.get('name_local'), poi.get('location_local'))
if photo_url:
    self.cache["pois"][cache_key] = photo_url
    self._save_cache()

    # 判断来源并显示
    if 'xiaohongshu' in photo_url or 'xhscdn' in photo_url:
        print("✓ (xiaohongshu)")
    else:
        print("✓")
else:
    print("✗")
```

---

### Phase 2: 改进无坐标POI的处理

#### 修改4: 添加中国城市列表fallback

**位置**: `_map_service_for()` lines 162-165

**当前逻辑**:
```python
if lng == 0.0 and lat == 0.0:
    self._country_cache[cache_key] = ""
    return "google"  # 盲目默认Google
```

**改进后**:
```python
if lng == 0.0 and lat == 0.0:
    # 尝试从中国城市列表判断
    china_cities = {
        'beijing', 'shanghai', 'guangzhou', 'shenzhen', 'chengdu',
        'chongqing', "xi'an", 'xian', 'hangzhou', 'wuhan', 'tianjin',
        'nanjing', 'suzhou', 'qingdao', 'dalian', 'xiamen', 'kunming',
        'guilin', 'zhangjiajie', 'bazhong', 'harbin', 'shenyang',
        'changsha', 'ningbo', 'dongguan', 'foshan', 'jinan'
    }

    city_lower = city.strip().lower()
    if city_lower in china_cities:
        logger.info(f"City '{city}' matched China cities list (no coordinates)")
        self._country_cache[cache_key] = "CN"
        return "gaode"

    # 真正的未知城市才用Google
    logger.warning(f"Cannot determine country for '{city}' - defaulting to Google")
    self._country_cache[cache_key] = ""
    return "google"
```

**效果**：
- 即使bucket-list的POI无坐标
- 只要城市名在列表中 → 使用Gaode
- 减少"中国POI用Google"的情况

---

### Phase 3: 验证小红书Skill可用性

#### 步骤1: 检查rednote skill安装

```bash
# 检查skill脚本存在
ls -la /root/travel-planner/.claude/skills/rednote/scripts/search.py

# 检查MCP server安装
npm list -g | grep rednote-mcp
```

#### 步骤2: 测试小红书搜索

```bash
cd /root/travel-planner
source venv/bin/activate

# 测试搜索
python .claude/skills/rednote/scripts/search.py "北京故宫" --limit 3

# 预期输出：
# {
#   "status": "success",
#   "data": [
#     {
#       "title": "...",
#       "images": ["https://..."],
#       ...
#     }
#   ]
# }
```

#### 步骤3: 如果skill不可用，安装rednote-mcp

```bash
# 全局安装MCP server
npm install -g @rednote/rednote-mcp-server

# 或在项目中安装
cd /root/travel-planner
npm install @rednote/rednote-mcp-server
```

---

### Phase 4: 清空缓存并重新提取（可选）

**仅在以下情况需要**：
- 想测试小红书fallback的覆盖率
- 想修正bucket-list的服务选择

#### 步骤1: 回退之前的错误commit（如果需要）

```bash
# 检查当前状态
git log --oneline -5

# 如果5f6619b引入了问题，回退
# （但根据分析，这个commit是合理的，无需回退）
```

#### 步骤2: 清空特定计划的缓存

```bash
cd /root/travel-planner

# 只清空bucket-list缓存（它们有无坐标问题）
for plan in china-exchange-bucket-list-2026 beijing-exchange-bucket-list-20260202-232405; do
  python3 << EOF
import json
with open("data/$plan/images.json") as f:
    cache = json.load(f)
cache["pois"] = {}
cache["city_covers"] = {}
with open("data/$plan/images.json", "w") as f:
    json.dump(cache, f, indent=2, ensure_ascii=False)
print(f"✓ Cleared cache for $plan")
EOF
done
```

#### 步骤3: 重新提取（测试小红书fallback）

```bash
source venv/bin/activate

# 重新提取bucket-list计划
python scripts/fetch-images-batch.py china-exchange-bucket-list-2026 999 999 --force
python scripts/fetch-images-batch.py beijing-exchange-bucket-list-20260202-232405 999 999 --force
```

**预期结果**：
- 高德/谷歌能找到的POI仍然从那里获取
- 之前"✗"失败的POI现在会尝试小红书
- 输出中会看到 "✓ (xiaohongshu)" 标记

---

## 验证标准

### 验证1: 小红书Fallback生效

**运行脚本时观察输出**：
```
Fetching Terracotta Army Museum (attraction, gaode)... ✗
  → Trying Xiaohongshu...
  → Found photo from Xiaohongshu for Terracotta Army Museum
  → ✓ (xiaohongshu)
```

**检查缓存**：
```bash
python3 << 'EOF'
import json

with open("data/china-exchange-bucket-list-2026/images.json") as f:
    cache = json.load(f)

xiaohongshu_urls = [url for url in cache["pois"].values()
                   if 'xiaohongshu' in url or 'xhscdn' in url]

print(f"小红书来源的图片: {len(xiaohongshu_urls)}")
for url in xiaohongshu_urls[:5]:
    print(f"  {url[:80]}...")
EOF
```

### 验证2: Orange Hotel修复验证

**修复前**: Orange Hotel使用Google服务
**修复后**: 应该使用Gaode服务

```bash
python3 << 'EOF'
import json

with open("data/china-feb-15-mar-7-2026-20260202-195429/images.json") as f:
    cache = json.load(f)

# 检查Orange Hotel的缓存键
orange_gaode = "gaode_桔子酒店北京中关村学院桥店"
orange_google = "google_Orange Hotel Beijing Zhongguancun Xueyuanqiao"

if orange_gaode in cache['pois']:
    print(f"✅ Orange Hotel使用Gaode服务 (正确)")
    print(f"   URL: {cache['pois'][orange_gaode][:80]}...")
elif orange_google in cache['pois']:
    print(f"❌ Orange Hotel仍然使用Google服务 (错误)")
    print(f"   URL: {cache['pois'][orange_google][:80]}...")
else:
    print("⚠️  Orange Hotel不在缓存中")
EOF
```

### 验证3: 服务选择统计

**主计划应该100% Gaode** (修复后):
```bash
python3 << 'EOF'
import json

with open("data/china-feb-15-mar-7-2026-20260202-195429/images.json") as f:
    cache = json.load(f)

gaode = [k for k in cache['pois'] if k.startswith('gaode_')]
google = [k for k in cache['pois'] if k.startswith('google_')]

print(f"china-feb-15-mar-7:")
print(f"  Gaode: {len(gaode)} ({len(gaode)/len(cache['pois'])*100:.1f}%)")
print(f"  Google: {len(google)} ({len(google)/len(cache['pois'])*100:.1f}%)")
print(f"\n修复后应该:")
print(f"  Gaode: 100%")
print(f"  Google: 0%")
EOF
```

### 验证4: 中国城市列表fallback生效

**测试无坐标的中国城市**：
```bash
python3 << 'EOF'
import sys
sys.path.insert(0, '/root/travel-planner/scripts')

# 模拟测试（需要修改后才能运行）
# from fetch_images_batch import ImageFetcher
# fetcher = ImageFetcher("test")
#
# # 测试无坐标的中国城市
# result = fetcher._map_service_for("Xi'an")  # 假设无坐标
# print(f"Xi'an (无坐标): {result}")  # 应该是 "gaode"
#
# result = fetcher._map_service_for("Hong Kong")  # 假设无坐标
# print(f"Hong Kong (无坐标): {result}")  # 应该是 "google"
EOF
```

---

## 关键文件

- `/root/travel-planner/scripts/fetch-images-batch.py` - 主要修改
  - Line 468后: 新增 `_xiaohongshu_search()`
  - Lines 450-468: 修改 `fetch_poi_photo()` 添加fallback链
  - Lines 162-169: 修改 `_map_service_for()` 添加中国城市列表
  - Lines 923-937: 更新输出显示来源

- `/root/travel-planner/.claude/skills/rednote/scripts/search.py` - 小红书skill
  - 验证存在性
  - 测试可用性

- `/root/travel-planner/data/*/images.json` - 缓存文件
  - 可选清空重新提取

---

## 不需要修改的部分

### ✅ 保持现状

1. **服务选择逻辑** - 已经正确
   - geopip检测工作正常
   - CN→Gaode，非CN→Google完全符合设计

2. **关键词搜索** - 已经正确
   - 100%使用关键词搜索
   - 无坐标搜索代码

3. **无坐标默认Google** - 合理的降级
   - 无法确定国家时的安全fallback
   - 通过中国城市列表改进即可

4. **缓存键格式** - 已经统一
   - Gaode: 中文键
   - Google: 英文键
   - 主计划97%纯净

---

## 总结

### 当前状态
- ✅ 服务选择：geopip逻辑正确
- ✅ 搜索方式：100%关键词搜索
- ❌ Bug：多城市location导致service选择错误（Orange Hotel）
- ❌ Fallback：缺少小红书fallback

### 修改内容（优先级排序）

#### 🔴 必须修复（Phase 0）：
**修复Orange Hotel Bug - 多城市Location问题**
- 问题：Day 8 location="Shanghai / Beijing"导致无法识别城市
- 影响：Orange Hotel有正确的北京坐标，但错误使用Google服务
- 方案：修改`_map_service_for()`支持POI自己的coordinates参数
- 效果：主计划100% Gaode（当前97%）

#### 🟡 核心功能（Phase 1）：
**添加小红书fallback**
- 补齐用户的第3条设计规则
- 高德/谷歌失败 → 自动尝试小红书
- 提升覆盖率，减少"✗"失败

#### 🟢 改进建议（Phase 2）：
**添加中国城市列表fallback**
- 改进无坐标POI的处理
- 通过城市名匹配判断是否在中国
- 减少bucket-list的Google使用率

#### 🟦 可选测试（Phase 4）：
**清空缓存重新提取**
- 测试所有修改的效果
- 验证小红书fallback覆盖率
- 确认Orange Hotel修复成功

### 修复后效果
- **Orange Hotel**：使用Gaode服务（当前错误用Google）
- **主计划**：100% Gaode（当前97%）
- **小红书fallback**：高德/谷歌失败的POI自动尝试小红书
- **无坐标处理**：中国城市通过列表识别，仍用Gaode
- **覆盖率提升**：减少"✗"失败，增加成功率

### 不需要回退
- commit `5f6619b` 是合理的，无需回退
- Bucket-list的混合使用是正常fallback行为
- 主计划的3% Google是真正的bug（Orange Hotel），需要修复
