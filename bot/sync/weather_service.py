"""
天气与日历信息获取模块
使用查表法获取农历和节气（无需计算）
天气使用 wttr.in 免费 API（无需密钥）
"""
import requests
import re
from datetime import datetime
from typing import Optional

# 导入查表法农历节气模块
from lunar_calendar import get_lunar_date_lookup, get_special_day

# 天气图标映射
WEATHER_ICONS = {
    'Sunny': '☀️', 'Clear': '☀️',
    'Partly cloudy': '⛅', 'Cloudy': '☁️',
    'Overcast': '☁️',
    'Mist': '🌫️', 'Fog': '🌫️',
    'Patchy rain possible': '🌦️', 'Patchy light rain': '🌦️',
    'Light rain': '🌧️', 'Moderate rain': '🌧️',
    'Heavy rain': '⛈️', 'Torrential rain': '⛈️',
    'Light snow': '🌨️', 'Moderate snow': '🌨️', 'Heavy snow': '❄️',
    'Thunder': '⚡', 'Thunderstorm': '⛈️',
}


class WeatherInfo:
    """天气信息"""
    
    def __init__(self, temp: int, condition: str, icon: str = "🌡️",
                 location: str = "上海"):
        self.temp = temp
        self.condition = condition
        self.icon = icon
        self.location = location
    
    def __str__(self) -> str:
        return f"{self.icon} {self.condition} {self.temp}°C"


def get_weather(location: str = "Shanghai") -> Optional[WeatherInfo]:
    """
    获取天气信息
    
    Args:
        location: 城市名或拼音（默认 Shanghai）
    
    Returns:
        WeatherInfo 对象，失败返回 None
    """
    try:
        # wttr.in API，禁用颜色代码
        url = f"https://wttr.in/{location}?format=%C|%t|%l&nonce=1"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return None
        
        parts = response.text.strip().split("|")
        if len(parts) < 2:
            return None
        
        condition = parts[0].strip()
        temp_str = parts[1].strip()  # 例如 "+12°C" 或 "-5°C"
        
        # 提取温度数字
        temp_match = re.search(r'[+-]?(\d+)', temp_str)
        if temp_match:
            temp = int(temp_match.group(1))
            if temp_str.startswith('-'):
                temp = -temp
        else:
            temp = 20  # 默认值
        
        # 匹配图标
        icon = "🌡️"
        for key, ic in WEATHER_ICONS.items():
            if key.lower() in condition.lower():
                icon = ic
                break
        
        return WeatherInfo(temp, condition, icon, location)
    
    except Exception as e:
        print(f"Weather fetch error: {e}")
        return None


def get_diary_header(date: Optional[datetime] = None, 
                     location: str = "Shanghai",
                     default_location: str = "Shanghai") -> str:
    """
    生成日记标题头
    
    格式：YYYY年M月D日 周X 天气emoji 农历X月XX [节气/节日] [· 城市]
    
    例如：
    - 默认城市：2026年2月20日 周四 🌤️ 正月廿三
    - 其他城市：2026年2月20日 周四 🌤️ 正月廿三 · 杭州
    """
    if date is None:
        date = datetime.now()
    
    # 完整日期和周几
    date_str = f"{date.year}年{date.month}月{date.day}日"
    weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    weekday_str = weekdays[date.weekday()]
    
    # 天气（仅emoji）
    weather = get_weather(location)
    weather_str = weather.icon if weather else "🌡️"
    
    # 农历日期（查表法）
    lunar = get_lunar_date_lookup(date)
    lunar_str = f" {lunar}" if lunar else ""
    
    # 节气/节日（查表法，仅当天有）
    special_day = get_special_day(date)
    special_str = f" {special_day}" if special_day else ""
    
    # 城市标注（非默认城市时显示）
    location_str = ""
    if location != default_location:
        # 将英文城市名转为中文显示
        city_names = {
            'Shanghai': '上海',
            'Beijing': '北京',
            'Hangzhou': '杭州',
            'Shenzhen': '深圳',
            'Chengdu': '成都',
            'Guangzhou': '广州',
            'Puer': '普洱',
            'Hong Kong': '香港',
        }
        city_display = city_names.get(location, location)
        location_str = f" · {city_display}"
    
    return f"{date_str} {weekday_str} {weather_str}{lunar_str}{special_str}{location_str}"


def get_diary_title_with_poem(date: Optional[datetime] = None,
                               location: str = "Shanghai",
                               poetic_desc: Optional[str] = None) -> str:
    """
    生成完整日记标题（包含可选诗意描述）
    
    优先格式：日期 周几 天气 农历 [节气/节日]
    次选：日期 周几 天气 农历 [诗意描述]
    """
    header = get_diary_header(date, location)
    
    # 如果有诗意描述且没有节气/节日，才附加
    if poetic_desc:
        if not get_special_day(date):
            return f"{header} · {poetic_desc}"
    
    return header


# =============== 向后兼容的别名 ===============
get_lunar_date = get_lunar_date_lookup
get_solar_term = get_special_day


if __name__ == "__main__":
    # 测试
    print("=== 天气测试 ===")
    weather = get_weather("Shanghai")
    if weather:
        print(f"天气: {weather}")
    
    print("\n=== 日记标题测试 ===")
    from datetime import datetime
    test_dates = [
        datetime(2026, 2, 17),  # 春节
        datetime(2026, 2, 18),  # 雨水
        datetime(2026, 2, 19),  # 正月初三
        datetime(2026, 2, 20),  # 无节气
    ]
    for d in test_dates:
        print(get_diary_header(d))
