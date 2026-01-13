#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
地理编码结果验证器 - 验证和校正地理编码结果

功能：
 - 行政区一致性检查
 - 坐标距离合理性检查
 - 分级回退查询策略
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple


# 中国主要城市中心点坐标（用于距离验证）
CITY_CENTERS = {
    "北京市": (39.9042, 116.4074),
    "上海市": (31.2304, 121.4737),
    "广州市": (23.1291, 113.2644),
    "深圳市": (22.5431, 114.0579),
    "杭州市": (30.2741, 120.1551),
    "南京市": (32.0603, 118.7969),
    "成都市": (30.5728, 104.0668),
    "重庆市": (29.4316, 106.9123),
    "武汉市": (30.5928, 114.3055),
    "西安市": (34.3416, 108.9398),
    "苏州市": (31.2989, 120.5853),
    "天津市": (39.0842, 117.2009),
    "南平市": (26.6417, 118.1780),
    "福州市": (26.0745, 119.2965),
    "长沙市": (28.2282, 112.9388),
    "郑州市": (34.7472, 113.6249),
    "济南市": (36.6512, 117.1201),
    "青岛市": (36.0671, 120.3826),
    "沈阳市": (41.8057, 123.4315),
    "大连市": (38.9140, 121.6147),
    "哈尔滨市": (45.8038, 126.5350),
    "长春市": (43.8171, 125.3235),
    "昆明市": (24.8801, 102.8329),
    "贵阳市": (26.6470, 106.6302),
    "南昌市": (28.6820, 115.8579),
    "合肥市": (31.8206, 117.2272),
    "石家庄市": (38.0428, 114.5149),
    "太原市": (37.8706, 112.5489),
    "兰州市": (36.0611, 103.8343),
    "乌鲁木齐市": (43.8256, 87.6168),
    "拉萨市": (29.6500, 91.1000),
    "西宁市": (36.6171, 101.7782),
    "银川市": (38.4872, 106.2309),
    "呼和浩特市": (40.8428, 111.7500),
    "南宁市": (22.8170, 108.3665),
    "海口市": (20.0444, 110.1999),
    "温州市": (28.0016, 120.6722),
    "宁波市": (29.8683, 121.5440),
    "无锡市": (31.4912, 120.3119),
    "厦门市": (24.4798, 118.0894),
}

# 合理距离阈值（单位：公里）
MAX_DISTANCE_FROM_CITY = {
    "province": 800,
    "city": 150,
    "district": 50,
    "street": 20,
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    计算两点间的球面距离（单位：公里）
    
    Args:
        lat1, lon1: 第一个点的纬度和经度
        lat2, lon2: 第二个点的纬度和经度
    
    Returns:
        距离（公里）
    """
    R = 6371  # 地球半径（公里）
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat/2)**2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def validate_locality_match(query_levels: List[str], result: Dict) -> Tuple[bool, str]:
    """
    检查返回结果的 locality 是否与查询的行政区一致
    
    Args:
        query_levels: 查询地址层级，如 ["浙江省", "杭州市", "上城区", "孤山路25号", "杭州博物馆"]
        result: API 返回的结果
    
    Returns:
        (是否通过, 原因说明)
    """
    result_locality = result.get("locality", "")
    result_formatted = result.get("formattedAddress", "") or result.get("display_name", "")
    
    # 提取查询中的省市区信息
    query_province = query_levels[0] if len(query_levels) >= 1 else ""
    query_city = query_levels[1] if len(query_levels) >= 2 else ""
    query_district = query_levels[2] if len(query_levels) >= 3 else ""
    
    # 检查1：locality 应该在查询的行政区范围内
    if result_locality:
        if query_district and query_district not in result_locality and query_district not in result_formatted:
            return False, f"locality 不匹配: 查询={query_district}, 返回={result_locality}"
        if query_city and query_city not in result_formatted:
            return False, f"city 不匹配: 查询={query_city}, 返回={result_formatted}"
    
    # 检查2：formattedAddress 应该包含查询的上级行政区
    if result_formatted:
        query_city_base = query_city.replace("市", "").replace("地区", "")
        result_formatted_normalized = result_formatted.replace("省", "").replace("市", "")
        
        if query_city_base and query_city_base not in result_formatted_normalized:
            return False, f"formattedAddress 不包含查询城市: 查询={query_city}, 返回={result_formatted}"
    
    return True, "通过"


def validate_coordinate_distance(query_levels: List[str], result: Dict) -> Tuple[bool, str]:
    """
    检查返回坐标是否在合理距离范围内
    
    Args:
        query_levels: 查询地址层级
        result: API 返回结果
    
    Returns:
        (是否通过, 原因说明)
    """
    result_lat = result.get("latitude") or result.get("lat")
    result_lon = result.get("longitude") or result.get("lon")
    
    if not result_lat or not result_lon:
        return True, "无坐标信息，跳过检查"
    
    # 获取查询的城市
    query_city = query_levels[1] if len(query_levels) >= 2 else None
    
    if not query_city or query_city not in CITY_CENTERS:
        return True, "无参考坐标，跳过检查"
    
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
        return False, f"距离异常: {query_city}中心 → 结果坐标 = {distance:.1f}km (阈值: {max_distance}km)"
    
    return True, f"距离正常: {distance:.1f}km"


def validate_geocode_result(
    query_levels: List[str], 
    result: Dict,
    check_locality: bool = True,
    check_distance: bool = True
) -> Dict:
    """
    综合验证地理编码结果
    
    Args:
        query_levels: 查询地址层级
        result: API 返回结果
        check_locality: 是否检查 locality
        check_distance: 是否检查距离
    
    Returns:
        验证结果字典
    """
    checks = []
    all_passed = True
    
    if check_locality:
        passed, reason = validate_locality_match(query_levels, result)
        checks.append({"check": "locality_match", "passed": passed, "reason": reason})
        if not passed:
            all_passed = False
    
    if check_distance:
        passed, reason = validate_coordinate_distance(query_levels, result)
        checks.append({"check": "distance_check", "passed": passed, "reason": reason})
        if not passed:
            all_passed = False
    
    return {
        "validation_passed": all_passed,
        "checks": checks
    }


def parse_address_levels(address: str, separator: str = "-") -> List[str]:
    """
    解析地址为层级列表
    
    Args:
        address: 完整地址，如 "浙江省-杭州市-上城区-孤山路25号-杭州博物馆"
        separator: 分隔符
    
    Returns:
        层级列表
    """
    return [level.strip() for level in address.split(separator) if level.strip()]
