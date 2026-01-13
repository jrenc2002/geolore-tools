#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
内容包构建器 - 将抽取和地理编码结果打包为 Geolore 格式

功能：
 - 生成符合 ContentPack v2 规范的 JSON
 - 支持时间序列（Timeline）
 - 自动去重与合并
"""

from __future__ import annotations

import json
import os
import re
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict


@dataclass
class PackConfig:
    """内容包配置"""
    pack_id: str
    version: int = 1
    title: Optional[str] = None
    locale: str = "zh-Hans"
    apply_mode: str = "merge"
    
    map_id: Optional[str] = None
    map_title: str = "地图"
    map_description: Optional[str] = None
    default_latitude: Optional[float] = None
    default_longitude: Optional[float] = None
    default_zoom: Optional[float] = None
    
    tags: Optional[List[str]] = None


def truncate_text(s: str, max_chars: int) -> str:
    """截断文本到指定长度"""
    s = re.sub(r"\s+", " ", (s or "").strip())
    return s if len(s) <= max_chars else s[: max_chars - 1] + "…"


def generate_client_id(prefix: str, name: str) -> str:
    """生成稳定的 clientId"""
    h = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{h}"


def build_place(
    name: str,
    geocode_result: Dict,
    client_id: Optional[str] = None,
    synopsis: Optional[str] = None,
    timeline: Optional[Dict] = None
) -> Optional[Dict]:
    """
    构建 place 对象
    
    Args:
        name: 地名
        geocode_result: 地理编码结果
        client_id: 自定义 clientId
        synopsis: 地点摘要
        timeline: 时间序列信息（v2）
    
    Returns:
        place 字典，编码失败返回 None
    """
    if not geocode_result:
        return None
    
    if client_id is None:
        # 优先使用 OSM ID
        osm_type = (geocode_result.get("osm_type") or "").lower()
        osm_id = geocode_result.get("osm_id")
        if osm_type and osm_id:
            client_id = f"osm-{osm_type}-{osm_id}"
        else:
            client_id = generate_client_id("place", name)
    
    place = {
        "clientId": client_id,
        "title": name,
        "latitude": geocode_result.get("lat") or geocode_result.get("latitude"),
        "longitude": geocode_result.get("lon") or geocode_result.get("longitude"),
    }
    
    # 可选字段
    if geocode_result.get("locality"):
        place["locality"] = geocode_result["locality"]
    if geocode_result.get("countryCode"):
        place["countryCode"] = geocode_result["countryCode"]
    if geocode_result.get("formattedAddress") or geocode_result.get("display_name"):
        place["formattedAddress"] = geocode_result.get("formattedAddress") or geocode_result.get("display_name")
    if synopsis:
        place["synopsis"] = synopsis
    if timeline:
        place["timeline"] = timeline
    
    return place


def build_map_place(
    place_client_id: str,
    order_index: int = 1,
    custom_title: Optional[str] = None,
    note: Optional[str] = None,
    pin_style: Optional[str] = None,
    note_max_len: int = 120
) -> Dict:
    """
    构建 mapPlace 对象
    
    Args:
        place_client_id: 引用的 place clientId
        order_index: 排序索引
        custom_title: 自定义标题
        note: 备注
        pin_style: 标注样式
        note_max_len: 备注最大长度
    
    Returns:
        mapPlace 字典
    """
    map_place = {
        "placeClientId": place_client_id,
        "orderIndex": order_index,
    }
    
    if custom_title:
        map_place["customTitle"] = custom_title
    if note:
        map_place["note"] = truncate_text(note, note_max_len)
    if pin_style:
        map_place["pinStyle"] = pin_style
    
    return map_place


def build_place_content(
    client_id: str,
    place_client_id: str,
    content_type: str,
    payload: Dict,
    order_index: int = 1,
    locale: Optional[str] = None
) -> Dict:
    """
    构建 placeContent 对象
    
    Args:
        client_id: 内容块 clientId
        place_client_id: 引用的 place clientId
        content_type: 内容类型（text/image/gallery/link/x-*）
        payload: 内容负载
        order_index: 排序索引
        locale: 语言代码
    
    Returns:
        placeContent 字典
    """
    content = {
        "clientId": client_id,
        "placeClientId": place_client_id,
        "type": content_type,
        "orderIndex": order_index,
        "payload": payload,
    }
    
    if locale:
        content["locale"] = locale
    
    return content


def build_content_pack(
    config: PackConfig,
    places: List[Dict],
    map_places: Optional[List[Dict]] = None,
    place_contents: Optional[List[Dict]] = None,
    schema_version: int = 1
) -> Dict:
    """
    构建完整的内容包
    
    Args:
        config: 包配置
        places: place 列表
        map_places: mapPlace 列表（如为 None 则自动生成）
        place_contents: placeContent 列表
        schema_version: 协议版本
    
    Returns:
        完整的内容包字典
    """
    # 自动生成 mapPlaces
    if map_places is None:
        map_places = []
        for i, place in enumerate(places, start=1):
            map_places.append({
                "placeClientId": place["clientId"],
                "orderIndex": i,
            })
    
    # 构建包元信息
    pack_meta = {
        "id": config.pack_id,
        "version": config.version,
    }
    if config.title:
        pack_meta["title"] = config.title
    pack_meta["locale"] = config.locale
    pack_meta["applyMode"] = config.apply_mode
    
    # 构建地图信息
    map_meta = {
        "title": config.map_title,
    }
    if config.map_id:
        map_meta["id"] = config.map_id
    if config.map_description:
        map_meta["descriptionText"] = config.map_description
    if config.default_latitude is not None:
        map_meta["defaultLatitude"] = config.default_latitude
    if config.default_longitude is not None:
        map_meta["defaultLongitude"] = config.default_longitude
    if config.default_zoom is not None:
        map_meta["defaultZoom"] = config.default_zoom
    
    # 构建标签
    tags = config.tags or []
    if "curated" not in tags:
        tags.insert(0, "curated")
    if not any(t.startswith("pack:") for t in tags):
        tags.append(f"pack:{config.pack_id}@{config.version}")
    
    # 组装内容包
    content_pack = {
        "schemaVersion": schema_version,
        "pack": pack_meta,
        "map": map_meta,
        "places": places,
        "mapPlaces": map_places,
        "tags": tags,
    }
    
    if place_contents:
        content_pack["placeContents"] = place_contents
    
    return content_pack


def write_content_pack(content_pack: Dict, output_path: str) -> None:
    """
    写入内容包到文件
    
    Args:
        content_pack: 内容包字典
        output_path: 输出文件路径
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(content_pack, f, ensure_ascii=False, indent=2)


def merge_places(places_list: List[Dict], key: str = "clientId") -> List[Dict]:
    """
    合并去重 places
    
    Args:
        places_list: place 列表
        key: 去重键
    
    Returns:
        去重后的 place 列表
    """
    seen = {}
    for place in places_list:
        k = place.get(key)
        if k and k not in seen:
            seen[k] = place
    return list(seen.values())
