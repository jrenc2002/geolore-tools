#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
高德地图 API 地理编码器

特点:
- 分级回退查询策略
- 结果验证机制（行政区一致性 + 距离合理性）
- 缓存支持（避免重复请求）
- 速率限制

使用示例:
  python amap.py \\
    --input filtered.json \\
    --output geocoded.json \\
    --amap-key YOUR_KEY \\
    --enable-validation
"""

from __future__ import annotations

import json
import math
import os
import time
import threading
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


# ==================== 城市中心坐标（用于距离验证）====================

CITY_CENTERS = {
    "北京市": (39.9042, 116.4074),
    "上海市": (31.2304, 121.4737),
    "天津市": (39.1244, 117.1944),
    "重庆市": (29.5630, 106.5516),
    "杭州市": (30.2741, 120.1551),
    "南京市": (32.0603, 118.7969),
    "苏州市": (31.2989, 120.5853),
    "武汉市": (30.5928, 114.3055),
    "成都市": (30.5728, 104.0668),
    "西安市": (34.3416, 108.9398),
    "南平市": (26.6417, 118.1780),
    "福州市": (26.0745, 119.2965),
    "厦门市": (24.4798, 118.0894),
    "广州市": (23.1291, 113.2644),
    "深圳市": (22.5431, 114.0579),
    "长沙市": (28.2282, 112.9388),
    "郑州市": (34.7466, 113.6254),
    "济南市": (36.6512, 117.1209),
    "青岛市": (36.0671, 120.3826),
    "沈阳市": (41.8057, 123.4315),
    "大连市": (38.9140, 121.6147),
    "哈尔滨市": (45.8038, 126.5340),
    "长春市": (43.8868, 125.3245),
    "昆明市": (25.0406, 102.7129),
    "贵阳市": (26.6470, 106.6302),
    "兰州市": (36.0611, 103.8343),
    "银川市": (38.4681, 106.2731),
    "乌鲁木齐市": (43.8256, 87.6168),
    "拉萨市": (29.6470, 91.1145),
    "呼和浩特市": (40.8416, 111.7519),
    "南昌市": (28.6829, 115.8579),
    "合肥市": (31.8206, 117.2272),
    "太原市": (37.8706, 112.5489),
    "石家庄市": (38.0428, 114.5149),
}

# 距离阈值（公里）
MAX_DISTANCE = {
    "province": 800,
    "city": 150,
    "district": 50,
    "street": 20,
}


# ==================== 工具函数 ====================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """计算两点间的球面距离（公里）"""
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def split_address_levels(address: str) -> List[str]:
    """分割地址层级"""
    parts = [p.strip() for p in str(address).split("-")]
    return [p for p in parts if p]


# ==================== 速率限制器 ====================

class RateLimiter:
    """令牌桶速率限制器"""
    
    def __init__(self, rate_per_sec: float = 30.0):
        self.rate = max(0.1, float(rate_per_sec))
        self.capacity = max(1, int(self.rate))
        self.tokens = float(self.capacity)
        self.timestamp = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self):
        while True:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.timestamp
                self.timestamp = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                need = (1.0 - self.tokens) / self.rate
            time.sleep(max(need, 0.001))


# ==================== 验证函数 ====================

def validate_locality_match(
    query_levels: List[str], 
    result: Dict[str, Any],
    verbose: bool = False
) -> bool:
    """验证返回结果的行政区是否与查询一致"""
    result_locality = result.get("locality", "")
    result_formatted = result.get("display_name", "") or ""
    
    query_province = query_levels[0] if len(query_levels) >= 1 else ""
    query_city = query_levels[1] if len(query_levels) >= 2 else ""
    query_district = query_levels[2] if len(query_levels) >= 3 else ""
    
    if result_locality:
        if query_district and query_district not in result_locality and query_district not in result_formatted:
            if verbose:
                print(f"  ⚠️ locality 不匹配: 查询={query_district}, 返回={result_locality}")
            return False
        if query_city and query_city not in result_formatted:
            query_city_base = query_city.replace("市", "").replace("地区", "").replace("自治州", "")
            if query_city_base and query_city_base not in result_formatted:
                if verbose:
                    print(f"  ⚠️ city 不匹配: 查询={query_city}, 返回={result_formatted}")
                return False
    return True


def validate_coordinate_distance(
    query_levels: List[str],
    result: Dict[str, Any],
    verbose: bool = False
) -> bool:
    """验证返回坐标是否在合理距离范围内"""
    result_lat = result.get("lat")
    result_lon = result.get("lon")
    
    if not result_lat or not result_lon:
        return True
    
    query_city = query_levels[1] if len(query_levels) >= 2 else None
    
    if not query_city or query_city not in CITY_CENTERS:
        return True
    
    city_lat, city_lon = CITY_CENTERS[query_city]
    distance = haversine_distance(city_lat, city_lon, result_lat, result_lon)
    
    if len(query_levels) >= 4:
        max_dist = MAX_DISTANCE["street"]
    elif len(query_levels) >= 3:
        max_dist = MAX_DISTANCE["district"]
    elif len(query_levels) >= 2:
        max_dist = MAX_DISTANCE["city"]
    else:
        max_dist = MAX_DISTANCE["province"]
    
    if distance > max_dist:
        if verbose:
            print(f"  ⚠️ 距离异常: {query_city}中心 → 结果 = {distance:.1f}km (阈值: {max_dist}km)")
        return False
    
    return True


# ==================== 高德 API 客户端 ====================

class AmapClient:
    """高德地图 API 客户端"""
    
    def __init__(self, api_key: str, rate_limit: float = 30.0):
        self.api_key = api_key
        self.limiter = RateLimiter(rate_limit)
        self.user_agent = "geolore-tools/1.0"
    
    def _http_get(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """发送 HTTP GET 请求"""
        self.limiter.acquire()
        full_url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(full_url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    
    def place_search(
        self, 
        keywords: str, 
        city: Optional[str] = None,
        citylimit: bool = True
    ) -> List[Dict[str, Any]]:
        """地点搜索 API"""
        params = {
            "key": self.api_key,
            "keywords": keywords,
            "offset": 1,
            "page": 1,
            "citylimit": "true" if citylimit else "false",
            "output": "JSON",
        }
        if city:
            params["city"] = city
        
        data = self._http_get("https://restapi.amap.com/v3/place/text", params)
        
        if str(data.get("status")) != "1":
            return []
        return data.get("pois") or []
    
    def geocode(
        self,
        address: str,
        city: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """地理编码 API"""
        params = {
            "key": self.api_key,
            "address": address,
            "output": "JSON",
        }
        if city:
            params["city"] = city
        
        data = self._http_get("https://restapi.amap.com/v3/geocode/geo", params)
        
        if str(data.get("status")) != "1":
            return []
        return data.get("geocodes") or []
    
    @staticmethod
    def normalize_poi(poi: Dict[str, Any]) -> Dict[str, Any]:
        """规范化 POI 结果"""
        loc = poi.get("location") or ""
        lon, lat = None, None
        try:
            if loc and "," in loc:
                parts = loc.split(",")
                lon = float(parts[0])
                lat = float(parts[1])
        except Exception:
            pass
        
        province = poi.get("pname")
        city = poi.get("cityname")
        district = poi.get("adname")
        
        return {
            "lat": lat,
            "lon": lon,
            "display_name": poi.get("name"),
            "amap_id": poi.get("id"),
            "address": {
                "province": province,
                "city": city,
                "district": district,
                "country_code": "cn",
            },
            "countryCode": "CN",
            "locality": district or city,
            "source": "amap",
        }
    
    @staticmethod
    def normalize_geocode(geo: Dict[str, Any]) -> Dict[str, Any]:
        """规范化地理编码结果"""
        loc = geo.get("location") or ""
        lon, lat = None, None
        try:
            if loc and "," in loc:
                parts = loc.split(",")
                lon = float(parts[0])
                lat = float(parts[1])
        except Exception:
            pass
        
        province = geo.get("province")
        city = geo.get("city")
        district = geo.get("district")
        
        return {
            "lat": lat,
            "lon": lon,
            "display_name": geo.get("formatted_address") or geo.get("level"),
            "address": {
                "province": province,
                "city": city,
                "district": district,
                "country_code": "cn",
            },
            "countryCode": "CN",
            "locality": district or city,
            "source": "amap",
        }


# ==================== 分级回退地理编码 ====================

def geocode_with_fallback(
    client: AmapClient,
    address: str,
    cache: Dict[str, Any],
    enable_validation: bool = True,
    verbose: bool = False,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    分级回退地理编码
    
    从最完整的地址开始，逐级向上回退，直到找到匹配结果。
    
    Args:
        client: 高德 API 客户端
        address: 地址字符串（如 "北京市-西城区-广安门外大街-广安门桥"）
        cache: 缓存字典
        enable_validation: 是否启用结果验证
        verbose: 是否打印详细日志
    
    Returns:
        (result, meta) - result 为地理编码结果，meta 为元数据
    """
    levels = split_address_levels(address)
    if not levels:
        return None, {"matchLevel": None, "matchMethod": None}
    
    meta = {
        "matchLevel": None,
        "matchMethod": None,
        "validationPassed": None,
    }
    
    # 从完整地址开始，逐级回退
    for num_levels in range(len(levels), 0, -1):
        query_parts = levels[:num_levels]
        query = "".join(query_parts)
        city = query_parts[0]  # 使用第一级作为 city 参数
        
        level_index = len(levels) - num_levels
        
        if verbose:
            print(f"  尝试 [{num_levels}级]: {query} (city={city})")
        
        # 检查缓存
        cache_key = f"amap:{query}"
        if cache_key in cache:
            cached = cache[cache_key]
            if cached:
                if verbose:
                    print(f"    ✓ 缓存命中")
                meta["matchLevel"] = level_index
                meta["matchMethod"] = "cache"
                meta["validationPassed"] = True
                return cached, meta
            else:
                if verbose:
                    print(f"    ✗ 缓存未命中（之前查询失败）")
                continue
        
        # 调用 API
        try:
            # 优先使用地点搜索
            pois = client.place_search(query, city=city, citylimit=True)
            
            if pois:
                result = client.normalize_poi(pois[0])
                
                # 验证结果
                if enable_validation:
                    locality_ok = validate_locality_match(levels, result, verbose)
                    distance_ok = validate_coordinate_distance(levels, result, verbose)
                    
                    if not locality_ok or not distance_ok:
                        if verbose:
                            print(f"    ⚠️ 验证失败，回退到上一级")
                        meta["validationPassed"] = False
                        continue
                
                # 缓存结果
                cache[cache_key] = result
                
                if verbose:
                    print(f"    ✓ 成功: ({result.get('lat')}, {result.get('lon')})")
                
                meta["matchLevel"] = level_index
                meta["matchMethod"] = "amap_place"
                meta["validationPassed"] = True
                return result, meta
            
            # 尝试地理编码 API
            geocodes = client.geocode(query, city=city)
            
            if geocodes:
                result = client.normalize_geocode(geocodes[0])
                
                if enable_validation:
                    locality_ok = validate_locality_match(levels, result, verbose)
                    distance_ok = validate_coordinate_distance(levels, result, verbose)
                    
                    if not locality_ok or not distance_ok:
                        if verbose:
                            print(f"    ⚠️ 验证失败，回退到上一级")
                        meta["validationPassed"] = False
                        continue
                
                cache[cache_key] = result
                
                if verbose:
                    print(f"    ✓ 成功 (geocode): ({result.get('lat')}, {result.get('lon')})")
                
                meta["matchLevel"] = level_index
                meta["matchMethod"] = "amap_geocode"
                meta["validationPassed"] = True
                return result, meta
            
            # 未找到结果
            cache[cache_key] = None
            if verbose:
                print(f"    ✗ 未找到")
                
        except Exception as e:
            cache[cache_key] = None
            if verbose:
                print(f"    ✗ 错误: {e}")
    
    return None, meta


# ==================== 主函数 ====================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="高德地图地理编码器")
    parser.add_argument("--input", "-i", required=True, help="输入 JSON 文件")
    parser.add_argument("--output", "-o", required=True, help="输出 JSON 文件")
    parser.add_argument("--amap-key", required=True, help="高德 API Key")
    parser.add_argument("--cache", default="geocode_cache.json", help="缓存文件路径")
    parser.add_argument("--enable-validation", action="store_true", help="启用结果验证")
    parser.add_argument("--disable-validation", action="store_true", help="禁用结果验证")
    parser.add_argument("--rate-limit", type=float, default=30.0, help="API 请求速率限制 (rps)")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()
    
    enable_validation = not args.disable_validation
    if args.enable_validation:
        enable_validation = True
    
    # 读取输入
    with open(args.input, "r", encoding="utf-8") as f:
        items = json.load(f)
    
    # 加载缓存
    cache = {}
    if os.path.exists(args.cache):
        try:
            with open(args.cache, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            pass
    
    # 初始化客户端
    client = AmapClient(args.amap_key, args.rate_limit)
    
    print(f"输入: {args.input} ({len(items)} 条)")
    print(f"验证: {'启用' if enable_validation else '禁用'}")
    print(f"缓存: {args.cache}")
    
    # 处理每个地点
    results = []
    success = 0
    failed = 0
    
    for i, item in enumerate(items):
        title = item.get("title", "")
        address = item.get("address", "")
        synopsis = item.get("synopsis", "")
        
        if args.verbose:
            print(f"\n[{i+1}/{len(items)}] {title}")
        
        result, meta = geocode_with_fallback(
            client=client,
            address=address,
            cache=cache,
            enable_validation=enable_validation,
            verbose=args.verbose,
        )
        
        output_item = {
            "title": title,
            "address": address,
            "synopsis": synopsis,
        }
        
        if result:
            output_item["latitude"] = result.get("lat")
            output_item["longitude"] = result.get("lon")
            output_item["locality"] = result.get("locality")
            output_item["countryCode"] = result.get("countryCode")
            output_item["formattedAddress"] = result.get("display_name")
            output_item["geocodeSource"] = "amap"
            output_item["matchLevel"] = meta.get("matchLevel")
            output_item["matchMethod"] = meta.get("matchMethod")
            output_item["validationPassed"] = meta.get("validationPassed")
            success += 1
        else:
            failed += 1
        
        results.append(output_item)
        
        # 定期保存缓存
        if (i + 1) % 10 == 0:
            with open(args.cache, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
    
    # 保存最终缓存
    with open(args.cache, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    
    # 保存输出
    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ 完成: {args.output}")
    print(f"  成功: {success}/{len(items)}")
    print(f"  失败: {failed}/{len(items)}")


if __name__ == "__main__":
    main()
