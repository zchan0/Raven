"""
Strava 自动同步调度器
支持多种触发方式
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SyncTrigger(Enum):
    """同步触发方式"""
    SCHEDULED = "scheduled"      # 定时触发
    WEBHOOK = "webhook"          # Strava Webhook
    MANUAL = "manual"            # 手动触发
    REAL_TIME = "realtime"       # 实时推送（需要 Strava 订阅）


@dataclass
class SyncConfig:
    """同步配置"""
    # 定时同步设置
    enabled: bool = True
    interval_minutes: int = 30  # 默认每30分钟检查一次
    
    # 实时同步（需要 Strava 付费订阅）
    use_webhook: bool = False
    webhook_url: Optional[str] = None
    
    # 过滤设置
    min_duration_seconds: int = 600  # 最短记录时间（10分钟）
    sync_private: bool = False       # 是否同步私密活动
    sync_commute: bool = False       # 是否同步通勤
    
    # 时间窗口
    lookback_hours: int = 24        # 同步过去多少小时的活动（默认当天）
    sync_today_only: bool = True    # 只同步今天的活动
    
    # 通知设置
    notify_on_sync: bool = True
    compact_mode: bool = False      # 使用精简消息


class StravaSyncScheduler:
    """Strava 同步调度器"""
    
    def __init__(self, strava_client, token_store, message_sender, 
                 groq_client=None, config: Optional[SyncConfig] = None):
        """
        Args:
            strava_client: Strava API 客户端
            token_store: Token 存储实例
            message_sender: 消息发送函数（如 Telegram bot）
            groq_client: Groq API 客户端（可选）
            config: 同步配置
        """
        self.strava = strava_client
        self.store = token_store
        self.send_message = message_sender
        self.groq = groq_client
        self.config = config or SyncConfig()
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """启动定时同步"""
        if self._running:
            logger.warning("Sync scheduler already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._scheduled_sync_loop())
        logger.info(f"Started Strava sync scheduler (interval: {self.config.interval_minutes}min)")
    
    async def stop(self):
        """停止同步"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped Strava sync scheduler")
    
    async def _scheduled_sync_loop(self):
        """定时同步循环"""
        while self._running:
            try:
                await self.sync_all_users()
            except Exception as e:
                logger.error(f"Scheduled sync failed: {e}")
            
            # 等待下次同步
            await asyncio.sleep(self.config.interval_minutes * 60)
    
    async def sync_all_users(self):
        """同步所有已授权用户"""
        # 从数据库获取所有用户
        user_ids = self.store.get_all_user_ids()
        
        for user_id in user_ids:
            try:
                await self.sync_user(user_id)
            except Exception as e:
                logger.error(f"Sync failed for user {user_id}: {e}")
                self.store.log_sync(user_id, None, 'failed', str(e))
    
    async def sync_user(self, user_id: int, trigger: SyncTrigger = SyncTrigger.SCHEDULED):
        """同步单个用户的 Strava 数据"""
        
        # 1. 获取 token
        token = self.store.get_token(user_id)
        if not token:
            logger.warning(f"No token found for user {user_id}")
            return
        
        # 2. 检查 token 是否过期，刷新 if needed
        if token.is_expired:
            logger.info(f"Token expired for user {user_id}, refreshing...")
            new_token = await self.strava.refresh_token(token.refresh_token)
            if new_token:
                self.store.save_token(user_id, new_token)
                token = new_token
            else:
                logger.error(f"Failed to refresh token for user {user_id}")
                return
        
        # 3. 获取上次同步时间
        last_sync = self.store.get_last_sync_time(user_id)
        
        # 4. 获取新活动（只检查当天）
        if self.config.sync_today_only:
            # 今天 00:00:00
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            after_timestamp = int(today.timestamp())
        else:
            after_timestamp = int(last_sync.timestamp()) if last_sync else None
        
        activities = await self.strava.get_activities(
            token.access_token,
            after=after_timestamp,
            per_page=10
        )
        
        if not activities:
            logger.debug(f"No new activities for user {user_id}")
            return
        
        # 5. 过滤活动
        filtered = self._filter_activities(activities)
        
        # 6. 处理每个活动
        for activity in filtered:
            try:
                await self._process_activity(user_id, activity)
            except Exception as e:
                logger.error(f"Failed to process activity {activity.get('id')}: {e}")
                self.store.log_sync(user_id, activity.get('id'), 'failed', str(e))
    
    def _filter_activities(self, activities: List[dict]) -> List[dict]:
        """过滤不符合条件的活动"""
        filtered = []
        
        for activity in activities:
            # 跳过太短的活动
            if activity.get('moving_time', 0) < self.config.min_duration_seconds:
                continue
            
            # 跳过私密活动（如果配置不允许）
            if activity.get('private') and not self.config.sync_private:
                continue
            
            # 跳过通勤（如果配置不允许）
            if activity.get('commute') and not self.config.sync_commute:
                continue
            
            filtered.append(activity)
        
        return filtered
    
    async def _process_activity(self, user_id: int, activity: dict):
        """处理单个活动并发送日记消息"""
        from strava_message_templates import ActivityFormatter, MessageTemplates
        from weather_service import get_diary_header
        from lunar_calendar import get_special_day
        
        activity_id = activity.get('id')
        
        # 1. 获取历史数据用于对比
        history = await self.strava.get_activities(
            self.store.get_token(user_id).access_token,
            per_page=20
        )
        
        # 2. 格式化数据
        display = ActivityFormatter.from_strava_activity(activity, history)
        
        # 3. 生成标题（新格式：日期 周几 天气 节气/节日）
        groq_title = None
        groq_insight = None
        
        if not self.config.compact_mode:
            # 获取运动日期
            start_dt = datetime.fromisoformat(
                activity.get('start_date_local', datetime.now().isoformat())
            )
            
            # 基础标题：日期 周几 天气 节气/节日
            base_title = get_diary_header(start_dt, location="Shanghai")
            
            # 尝试生成诗意描述（低优先级，仅在没有节气时附加）
            if self.groq:
                try:
                    poetic_desc = await self._generate_poetic_desc(display)
                    has_special_day = get_special_day(start_dt) is not None
                    if poetic_desc and not has_special_day:
                        # 如果有诗意描述且当天没有特殊节气/节日，附加到标题
                        groq_title = f"{base_title} · {poetic_desc}"
                    else:
                        groq_title = base_title
                except Exception as e:
                    logger.warning(f"Poetic desc generation failed: {e}")
                    groq_title = base_title
            else:
                groq_title = base_title
            
            # 生成洞察
            if self.groq:
                try:
                    groq_insight = await self._generate_insight_with_groq(display, history)
                except Exception as e:
                    logger.warning(f"Groq insight generation failed: {e}")
        
        # 4. 生成消息
        if self.config.compact_mode:
            message = MessageTemplates.create_compact_message(display)
        else:
            message = MessageTemplates.create_full_message(
                display, groq_title, groq_insight
            )
        
        # 5. 发送消息
        await self.send_message(user_id=user_id, text=message)
        
        # 6. 记录同步成功
        self.store.log_sync(user_id, activity_id, 'success')
        
        logger.info(f"Synced activity {activity_id} for user {user_id}")
    
    async def _generate_poetic_desc(self, display) -> Optional[str]:
        """生成诗意描述（低优先级，仅作为补充）"""
        if not self.groq:
            return None
        
        prompt = f"""为这次运动生成一个简短的中文诗意描述（6-10字），作为日记标题的可选补充。

运动信息：
- 类型：{display.sport_type}
- 距离：{display.distance_km} 公里
- 时间：{display.start_time}

要求：
1. 简短优美，有意境
2. 6-10 个汉字
3. 直接返回描述，不要加引号或解释
4. 如果没有灵感，返回"无"

描述："""
        
        try:
            response = await self.groq.generate(prompt, max_tokens=30)
            desc = response.strip().strip('"').strip("'")
            return None if desc == "无" else desc
        except Exception as e:
            logger.error(f"Poetic desc generation failed: {e}")
            return None

    async def _generate_title_with_groq(self, display) -> Optional[str]:
        """【已弃用】使用 Groq 生成诗意标题 - 保留用于兼容"""
        # 这个方法现在不直接使用，改为通过天气信息生成标题
        return await self._generate_poetic_desc(display)
    
    async def _generate_insight_with_groq(self, display, history) -> Optional[str]:
        """使用 Groq 生成运动洞察"""
        if not self.groq:
            return None
        
        # 简化版：如果提供了洞察才显示
        if not display.vs_last_time and not display.avg_hr:
            return None
        
        prompt = f"""根据运动数据生成一句简短的鼓励或观察（20字以内）。

数据：
- 配速：{display.pace}/km
{f'- 对比：{display.vs_last_time}' if display.vs_last_time else ''}
{f'- 心率：{display.avg_hr}bpm ({display.hr_zone}区)' if display.avg_hr else ''}

要求：自然、简洁、像朋友聊天。直接返回句子，不要加引号。

观察："""
        
        try:
            response = await self.groq.generate(prompt, max_tokens=60)
            return response.strip().strip('"').strip("'")
        except Exception as e:
            logger.error(f"Groq insight generation failed: {e}")
            return None
    
    async def handle_webhook(self, user_id: int, activity_id: int):
        """处理 Strava Webhook 回调（实时推送）"""
        # 1. 获取活动详情
        token = self.store.get_token(user_id)
        if not token:
            return
        
        activity = await self.strava.get_activity(token.access_token, activity_id)
        if not activity:
            return
        
        # 2. 检查是否应该同步
        if activity.get('moving_time', 0) < self.config.min_duration_seconds:
            logger.debug(f"Activity {activity_id} too short, skipping")
            return
        
        # 3. 处理活动
        await self._process_activity(user_id, activity)
        logger.info(f"Processed webhook for activity {activity_id}")
    
    async def force_sync(self, user_id: int, days: int = 7):
        """强制同步过去 N 天的活动（手动触发）"""
        logger.info(f"Force sync for user {user_id}, last {days} days")
        
        # 临时修改 lookback
        original_lookback = self.config.lookback_days
        self.config.lookback_days = days
        
        try:
            await self.sync_user(user_id, trigger=SyncTrigger.MANUAL)
        finally:
            self.config.lookback_days = original_lookback


# 使用示例
async def main():
    """示例：启动同步调度器"""
    from strava_token_store import TokenStore
    
    # 初始化组件
    token_store = TokenStore("./data/strava.db")
    
    # 模拟消息发送函数
    async def send_message(user_id: int, text: str):
        print(f"[To {user_id}]:\n{text}\n")
    
    # 配置
    config = SyncConfig(
        interval_minutes=30,      # 每30分钟检查
        min_duration_seconds=600, # 至少10分钟的运动
        notify_on_sync=True,
        compact_mode=False        # 完整消息模式
    )
    
    # 创建调度器（需要实际的 strava_client 和 groq_client）
    # scheduler = StravaSyncScheduler(
    #     strava_client=...,
    #     token_store=token_store,
    #     message_sender=send_message,
    #     groq_client=...,
    #     config=config
    # )
    
    # 启动
    # await scheduler.start()
    
    # 运行一段时间后停止
    # await asyncio.sleep(3600)
    # await scheduler.stop()


if __name__ == "__main__":
    # 测试消息模板
    from strava_message_templates import ActivityFormatter, MessageTemplates
    
    mock_activity = {
        'name': '晨跑',
        'sport_type': 'Run',
        'distance': 5230,
        'moving_time': 2028,
        'average_heartrate': 156,
        'max_heartrate': 175,
        'total_elevation_gain': 45,
        'calories': 312,
        'start_date_local': '2026-02-18T07:32:00+08:00'
    }
    
    display = ActivityFormatter.from_strava_activity(mock_activity)
    message = MessageTemplates.create_full_message(
        display,
        groq_title="晨光中的五公里独白",
        groq_insight="今天心率控制不错，轻松跑的节奏很稳 🌅"
    )
    
    print(message)
