"""
Strava 运动数据 → 日记消息模板
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List
import math

@dataclass
class ActivityDisplay:
    """用于展示的运动数据"""
    # 基础信息
    title: str              # 活动名称
    sport_type: str         # 运动类型
    sport_emoji: str        # 运动图标
    
    # 距离
    distance_km: float      # 公里
    distance_mi: float      # 英里（备用）
    
    # 时间
    duration: str           # 格式化时间 MM'SS"
    duration_seconds: int   # 原始秒数
    
    # 配速/速度
    pace: str               # 配速 MM'SS"/km
    speed: float            # 速度 km/h
    
    # 心率
    avg_hr: Optional[int]
    max_hr: Optional[int]
    hr_zone: Optional[str]  # 心率区间描述
    
    # 其他
    elevation: Optional[int]  # 爬升（米）
    calories: Optional[int]   # 卡路里
    
    # 时间信息
    start_time: str         # 开始时间（如 07:32）
    week_day: str           # 星期几
    
    # 对比数据（如果有历史）
    vs_last_time: Optional[str]  # 与上次对比
    vs_best_time: Optional[str]  # 与最佳对比


class ActivityFormatter:
    """运动数据格式化器"""
    
    SPORT_EMOJI = {
        'Run': '🏃‍♀️',
        'Ride': '🚴‍♀️',
        'Swim': '🏊‍♀️',
        'Walk': '🚶‍♀️',
        'Hike': '🥾',
        'Yoga': '🧘‍♀️',
        'WeightTraining': '🏋️‍♀️',
        'Workout': '💪',
        'Ski': '⛷️',
        'Snowboard': '🏂',
        'Rowing': '🚣‍♀️',
        'Elliptical': '🌀',
        'Other': '📍'
    }
    
    HR_ZONES = [
        (0, 100, '热身'),
        (100, 120, '燃脂'),
        (120, 140, '有氧'),
        (140, 160, '耐力'),
        (160, 180, '阈值'),
        (180, 999, '极限')
    ]
    
    @classmethod
    def format_duration(cls, seconds: int) -> str:
        """格式化持续时间"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}'{secs:02d}"
    
    @classmethod
    def format_pace(cls, distance_m: float, time_sec: int) -> str:
        """计算并格式化配速（每公里）"""
        if distance_m == 0:
            return "--'--"
        pace_sec = time_sec / (distance_m / 1000)
        minutes = int(pace_sec // 60)
        seconds = int(pace_sec % 60)
        return f"{minutes}'{seconds:02d}"
    
    @classmethod
    def get_hr_zone(cls, hr: int) -> str:
        """获取心率区间描述"""
        for min_hr, max_hr, desc in cls.HR_ZONES:
            if min_hr <= hr < max_hr:
                return desc
        return "未知"
    
    @classmethod
    def from_strava_activity(cls, activity: dict, 
                            history: Optional[List[dict]] = None) -> ActivityDisplay:
        """从 Strava API 返回的数据创建显示对象"""
        
        distance_m = activity.get('distance', 0)
        moving_time = activity.get('moving_time', 0)
        sport_type = activity.get('sport_type', 'Other')
        
        # 计算对比数据
        vs_last = None
        vs_best = None
        if history and len(history) > 1:
            # 找同类型上次运动
            same_type = [h for h in history if h['sport_type'] == sport_type]
            if len(same_type) > 1:
                last_time = same_type[1]['moving_time']
                diff = moving_time - last_time
                if abs(diff) < 60:
                    vs_last = f"与上次持平"
                elif diff < 0:
                    vs_last = f"比上次快 {cls.format_duration(abs(diff))}"
                else:
                    vs_last = f"比上次慢 {cls.format_duration(diff)}"
        
        start_dt = datetime.fromisoformat(
            activity.get('start_date_local', datetime.now().isoformat())
        )
        
        return ActivityDisplay(
            title=activity.get('name', '未命名运动'),
            sport_type=sport_type,
            sport_emoji=cls.SPORT_EMOJI.get(sport_type, '📍'),
            distance_km=round(distance_m / 1000, 2),
            distance_mi=round(distance_m / 1609.34, 2),
            duration=cls.format_duration(moving_time),
            duration_seconds=moving_time,
            pace=cls.format_pace(distance_m, moving_time),
            speed=round((distance_m / 1000) / (moving_time / 3600), 1) if moving_time > 0 else 0,
            avg_hr=activity.get('average_heartrate'),
            max_hr=activity.get('max_heartrate'),
            hr_zone=cls.get_hr_zone(activity.get('average_heartrate', 0)) if activity.get('average_heartrate') else None,
            elevation=round(activity.get('total_elevation_gain', 0)) if activity.get('total_elevation_gain') else None,
            calories=round(activity.get('calories', 0)) if activity.get('calories') else None,
            start_time=start_dt.strftime('%H:%M'),
            week_day=cls._get_week_day(start_dt),
            vs_last_time=vs_last,
            vs_best_time=vs_best
        )
    
    @staticmethod
    def _get_week_day(dt: datetime) -> str:
        """获取中文星期几"""
        days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        return days[dt.weekday()]


class MessageTemplates:
    """日记消息模板"""
    
    @staticmethod
    def create_full_message(data: ActivityDisplay, 
                           groq_title: Optional[str] = None,
                           groq_insight: Optional[str] = None) -> str:
        """
        生成完整日记消息
        
        格式：
        🏃‍♀️ 标题 | 距离 | 时间
        
        📊 数据
        • 配速/速度
        • 心率
        • 爬升/卡路里
        
        💡 Groq 洞察（可选）
        
        📝 体感记录（留给用户）
        
        ---
        同步自 Strava · 时间
        """
        
        # 标题行
        if groq_title:
            title_line = f"{data.sport_emoji} {groq_title}"
        else:
            title_line = f"{data.sport_emoji} {data.title} | {data.distance_km}km | {data.duration}"
        
        lines = [title_line, ""]
        
        # 数据行
        lines.append("📊 数据速览")
        lines.append(f"• 配速：{data.pace}/km")
        
        if data.avg_hr:
            hr_info = f"{data.avg_hr}bpm"
            if data.hr_zone:
                hr_info += f" ({data.hr_zone}区)"
            if data.max_hr:
                hr_info += f" 峰值{data.max_hr}"
            lines.append(f"• 心率：{hr_info}")
        
        if data.elevation:
            lines.append(f"• 爬升：{data.elevation}m")
        
        if data.calories:
            lines.append(f"• 消耗：{data.calories}kcal")
        
        # 对比
        if data.vs_last_time:
            lines.append(f"• 对比：{data.vs_last_time}")
        
        lines.append("")
        
        # Groq 洞察
        if groq_insight:
            lines.append(f"💡 {groq_insight}")
            lines.append("")
        
        # 用户补充区域
        lines.append("📝 体感记录")
        lines.append("[今天状态如何？天气怎样？有什么想记录的吗？]")
        lines.append("")
        
        # 页脚
        lines.append(f"---")
        lines.append(f"📍 同步自 Strava · {data.week_day} {data.start_time}")
        
        return "\n".join(lines)
    
    @staticmethod
    def create_compact_message(data: ActivityDisplay) -> str:
        """精简版消息（用于快速同步）"""
        lines = [
            f"{data.sport_emoji} {data.title}",
            f"📏 {data.distance_km}km · ⏱️ {data.duration} · 🏃 {data.pace}/km"
        ]
        
        if data.avg_hr:
            lines.append(f"❤️ {data.avg_hr}bpm")
        
        lines.append(f"\n📍 Strava · {data.start_time}")
        
        return "\n".join(lines)
    
    @staticmethod
    def create_first_sync_welcome(athlete_name: str) -> str:
        """首次同步欢迎消息"""
        return f"""🎉 Strava 连接成功！

欢迎 {athlete_name}，
你的运动数据将自动同步到日记中。

💡 小贴士：
• 每次运动后约 5 分钟会自动同步
• 你可以在消息中补充体感记录
• 点击消息可以查看完整运动数据

开始记录你的运动生活吧！
"""


# 使用示例
if __name__ == "__main__":
    # 模拟 Strava API 返回的数据
    mock_activity = {
        'name': '晨跑',
        'sport_type': 'Run',
        'distance': 5230,  # 米
        'moving_time': 2028,  # 秒 = 33'48"
        'elapsed_time': 2100,
        'total_elevation_gain': 45,
        'average_heartrate': 156,
        'max_heartrate': 175,
        'calories': 312,
        'start_date_local': '2026-02-18T07:32:00+08:00',
        'average_speed': 2.58,  # m/s
        'max_speed': 3.5
    }
    
    # 格式化数据
    display = ActivityFormatter.from_strava_activity(mock_activity)
    
    # 生成完整消息
    message = MessageTemplates.create_full_message(
        display,
        groq_title="晨光中的五公里独白",
        groq_insight="今天心率控制不错，轻松跑的节奏很稳 🌅"
    )
    
    print(message)
    print("\n" + "="*50 + "\n")
    
    # 生成精简消息
    compact = MessageTemplates.create_compact_message(display)
    print(compact)
