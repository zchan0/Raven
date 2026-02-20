"""
位置服务模块
基于坐标获取天气和位置信息
"""
import requests
from typing import Optional, Tuple, List

# 城市坐标数据库（可扩展）
CITY_COORDS = {
    'Shanghai': (31.2304, 121.4737),
    'Beijing': (39.9042, 116.4074),
    'Hangzhou': (30.2741, 120.1551),
    'Shenzhen': (22.5431, 114.0579),
    'Chengdu': (30.5728, 104.0668),
    'Guangzhou': (23.1291, 113.2644),
    'Puer': (22.8253, 100.9665),  # 普洱
    'Hong Kong': (22.3193, 114.1694),
    'Tokyo': (35.6762, 139.6503),
}


def get_nearest_city(lat: float, lng: float) -> Optional[str]:
    """
    根据坐标找到最近的城市
    
    Args:
        lat: 纬度
        lng: 经度
        
    Returns:
        城市英文名，找不到返回 None
    """
    min_distance = float('inf')
    nearest_city = None
    
    for city, (city_lat, city_lng) in CITY_COORDS.items():
        # 简化的距离计算（欧几里得距离，小范围可用）
        distance = ((lat - city_lat) ** 2 + (lng - city_lng) ** 2) ** 0.5
        if distance < min_distance:
            min_distance = distance
            nearest_city = city
    
    # 距离阈值：0.5度约等于50公里
    if min_distance < 0.5:
        return nearest_city
    
    return None


def get_city_from_strava_activity(activity: dict) -> Optional[str]:
    """
    从 Strava 活动数据中提取城市
    
    优先级：
    1. Strava 提供的 location_city
    2. 坐标反查最近城市
    3. 默认 None（使用配置）
    """
    # 1. 使用 Strava 的城市信息
    city = activity.get('location_city')
    if city:
        return city
    
    # 2. 使用坐标反查
    start_latlng = activity.get('start_latlng')
    if start_latlng and len(start_latlng) == 2:
        lat, lng = start_latlng
        nearest = get_nearest_city(lat, lng)
        if nearest:
            return nearest
    
    # 3. 无法识别
    return None


# =============== 反向地理编码（可选）===============
def reverse_geocode(lat: float, lng: float) -> Optional[str]:
    """
    使用 OpenStreetMap Nominatim 进行反向地理编码
    
    注意：生产环境需要考虑 API 限制和缓存
    """
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}&format=json"
        response = requests.get(url, timeout=5, headers={'User-Agent': 'MuninBot/1.0'})
        if response.status_code == 200:
            data = response.json()
            # 提取城市名
            address = data.get('address', {})
            city = address.get('city') or address.get('town') or address.get('village')
            return city
    except Exception:
        pass
    
    return None
