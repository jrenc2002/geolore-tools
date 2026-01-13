#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OSM Nominatim 地理编码器 - 使用 OpenStreetMap 免费 API 进行地理编码

功能：
 - 支持中文地名查询
 - 自动缓存查询结果
 - 遵守 API 速率限制
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional


USER_AGENT = "geolore-geocoder/0.1 (+https://github.com/jrenc2002/geolore-tools)"


def nominatim_search(
    query: str, 
    lang: str = "zh-CN",
    limit: int = 1,
    timeout: int = 20
) -> List[Dict]:
    """
    调用 Nominatim API 搜索地点
    
    Args:
        query: 搜索查询
        lang: 语言代码
        limit: 返回结果数量
        timeout: 超时时间（秒）
    
    Returns:
        搜索结果列表
    """
    base = "https://nominatim.openstreetmap.org/search"
    params = {
        "format": "jsonv2", 
        "q": query, 
        "addressdetails": 1, 
        "limit": limit,
        "accept-language": lang
    }
    url = f"{base}?{urllib.parse.urlencode(params)}"
    
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        return json.loads(data.decode("utf-8"))


def parse_nominatim_result(item: Dict) -> Dict:
    """
    解析 Nominatim 返回结果
    
    Args:
        item: Nominatim 结果项
    
    Returns:
        标准化的地点信息
    """
    address = item.get("address", {})
    
    # 提取 locality（优先级：city > town > county > state_district > state）
    locality = (
        address.get("city") or 
        address.get("town") or 
        address.get("county") or 
        address.get("state_district") or 
        address.get("state")
    )
    
    return {
        "lat": float(item.get("lat")),
        "lon": float(item.get("lon")),
        "display_name": item.get("display_name"),
        "osm_id": item.get("osm_id"),
        "osm_type": item.get("osm_type"),
        "address": address,
        "countryCode": address.get("country_code", "").upper(),
        "locality": locality,
        "place_type": item.get("type"),
        "importance": item.get("importance"),
    }


def geocode_single(
    name: str,
    lang: str = "zh-CN",
    timeout: int = 20
) -> Optional[Dict]:
    """
    对单个地名进行地理编码
    
    Args:
        name: 地名
        lang: 语言代码
        timeout: 超时时间
    
    Returns:
        地点信息，未找到返回 None
    """
    try:
        results = nominatim_search(name, lang=lang, limit=1, timeout=timeout)
        if results:
            return parse_nominatim_result(results[0])
        return None
    except Exception as e:
        print(f"Error geocoding '{name}': {e}")
        return None


def geocode_batch(
    names: List[str],
    cache_path: Optional[str] = None,
    sleep_sec: float = 1.0,
    lang: str = "zh-CN"
) -> Dict[str, Optional[Dict]]:
    """
    批量地理编码
    
    Args:
        names: 地名列表
        cache_path: 缓存文件路径
        sleep_sec: 请求间隔（秒），遵守 Nominatim 使用策略
        lang: 语言代码
    
    Returns:
        {地名: 地点信息} 字典
    """
    # 加载缓存
    cache = {}
    if cache_path and os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}
    
    results = {}
    
    for name in names:
        if not name:
            continue
            
        # 检查缓存
        if name in cache:
            results[name] = cache[name]
            continue
        
        print(f"Geocoding: {name}...")
        
        # 调用 API
        result = geocode_single(name, lang=lang)
        results[name] = result
        cache[name] = result
        
        # 写入缓存
        if cache_path:
            os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        
        # 速率限制
        time.sleep(sleep_sec)
    
    return results


def generate_client_id(rec: Dict, fallback_name: str) -> str:
    """
    生成稳定的 clientId
    
    Args:
        rec: 地理编码结果
        fallback_name: 备用名称
    
    Returns:
        clientId 字符串
    """
    osm_type = (rec.get("osm_type") or "").lower()
    osm_id = rec.get("osm_id")
    
    if osm_type and osm_id:
        return f"osm-{osm_type}-{osm_id}"
    
    import hashlib
    h = hashlib.sha1(fallback_name.encode("utf-8")).hexdigest()[:10]
    return f"name-{h}"
