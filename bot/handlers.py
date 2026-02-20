"""
Telegram 消息处理器

处理用户通过 Telegram 发送的各种消息：
- 文本消息 → 添加到日记
- 图片消息 → 保存到日记 + 上传到仓库
- 标签解析（如 #读书 #思考）
- /end 命令 → 立即合并当天日记
"""

from __future__ import annotations

import io
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    filters,
)
from telegram.ext import (
    MessageHandler as TelegramMessageHandler,
)

from .config import Config
from .diary_service import DiaryService
from .github_client import GitHubClient
from .scheduler import DiaryScheduler
from .storage import Storage

if TYPE_CHECKING:
    from telegram import PhotoSize

logger = logging.getLogger(__name__)


def extract_tags(text: str, exclude_label: str | None = None) -> list[str]:
    """
    从文本中提取 #标签。

    Args:
        text: 输入文本
        exclude_label: 要排除的标签（如 journal）

    Returns:
        标签列表（去重）
    """
    # 匹配 #标签（支持中文）
    pattern = r"#([\w\u4e00-\u9fa5]+)"
    matches = re.findall(pattern, text)

    # 去重 + 过滤掉指定标签
    tags = list(dict.fromkeys(matches))
    if exclude_label:
        tags = [t for t in tags if t != exclude_label]

    return tags


class BotHandlers:
    """Telegram Bot 处理器集合"""

    def __init__(self, config: Config, github: GitHubClient):
        self.config = config
        self.github = github

        # 初始化存储和服务
        self.storage = Storage()
        self.diary_service = DiaryService(self.storage, config, github)
        self.scheduler = DiaryScheduler(self.diary_service)

    async def start_scheduler(self):
        """启动调度器（需要在异步上下文中调用）"""
        await self.scheduler.start()

    def get_handlers(self):
        """获取所有处理器"""
        return [
            CommandHandler("config", self.handle_config),
            CommandHandler("end", self.handle_end),
            CommandHandler("start", self.handle_start),
            CommandHandler("help", self.handle_help),
            CommandHandler("reload", self.handle_reload),
            TelegramMessageHandler(filters.LOCATION, self.handle_location),
            TelegramMessageHandler(filters.TEXT | filters.PHOTO, self.handle_message),
        ]

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /start 命令"""
        await update.message.reply_text(
            "📔 Munin 日记机器人\n\n"
            "随手记录，自动成文。\n\n"
            "发送文字或图片来记日记\n"
            "用 #标签 分类整理\n"
            "每天自动发布到博客\n\n"
            "常用命令:\n"
            "/help - 详细使用说明\n"
            "/end - 立即合并今日日记\n"
            "/config - 查看/修改配置"
        )

    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /help 命令"""
        await update.message.reply_text(
            "📝 如何使用:\n\n"
            "**发送消息:**\n"
            "• 直接发文字，或发图片\n"
            "• 单张图可带文字说明（发图时加 Caption）\n"
            "• 多张图请分开发送，每张都会记录\n"
            "• 文字在前，图片在后显示\n\n"
            "**标签:**\n"
            "• 用 #标签 分类，如 #读书 #思考\n"
            "• 支持中英文标签\n\n"
            "**合并:**\n"
            "• 每天 00:00 自动合并到 GitHub\n"
            "• 或手动发送 /end 立即合并\n\n"
            "**配置:**\n"
            "• /config - 查看配置\n"
            "• /config time on|off - 时间显示\n"
            "• /config format 24h|12h - 时间格式\n"
            "• /config location - 设置天气位置\n"
            "• /reload - 重新加载菜单\n\n"
            "**示例:**\n"
            "今天读了一本书 #读书\n"
            "[图片] 咖啡和阳光 #生活"
        )

    async def handle_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /config 命令"""
        user_id = update.effective_user.id

        # 权限检查
        if not self._check_permission(user_id):
            await update.message.reply_text("⚠️ 你没有权限使用这个 bot")
            return

        # 解析命令参数
        args = context.args
        if not args:
            # 显示当前配置
            config = self.storage.get_user_config(user_id)
            time_status = "开启" if config.get("show_entry_time", True) else "关闭"
            time_format = config.get("entry_time_format", "%H:%M")

            await update.message.reply_text(
                f"⚙️ 当前配置:\n\n"
                f"时间显示: {time_status}\n"
                f"时间格式: {time_format}\n\n"
                f"修改配置:\n"
                f"/config time on - 开启时间显示\n"
                f"/config time off - 关闭时间显示\n"
                f"/config format 24h - 24小时制\n"
                f"/config format 12h - 12小时制"
            )
            return

        # 处理配置命令
        key = args[0].lower()

        if key == "time" and len(args) >= 2:
            value = args[1].lower()
            if value in ("on", "true", "1"):
                self.storage.set_user_config(user_id, "show_entry_time", 1)
                await update.message.reply_text("✅ 已开启时间显示")
            elif value in ("off", "false", "0"):
                self.storage.set_user_config(user_id, "show_entry_time", 0)
                await update.message.reply_text("✅ 已关闭时间显示")
            else:
                await update.message.reply_text("❌ 用法: /config time on|off")

        elif key == "format" and len(args) >= 2:
            value = args[1].lower()
            if value == "24h":
                self.storage.set_user_config(user_id, "entry_time_format", "%H:%M")
                await update.message.reply_text("✅ 已设置为24小时制 (16:30)")
            elif value == "12h":
                self.storage.set_user_config(user_id, "entry_time_format", "%I:%M %p")
                await update.message.reply_text("✅ 已设置为12小时制 (04:30 PM)")
            else:
                await update.message.reply_text("❌ 用法: /config format 24h|12h")

        elif key == "location":
            # 请求用户分享位置
            location_button = KeyboardButton(
                text="📍 分享当前位置",
                request_location=True
            )
            default_button = KeyboardButton("🏠 使用默认城市")
            
            reply_markup = ReplyKeyboardMarkup(
                keyboard=[[location_button], [default_button]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await update.message.reply_text(
                "请分享您的位置，以便获取当地天气信息：",
                reply_markup=reply_markup
            )

        else:
            await update.message.reply_text(
                "❌ 未知配置命令\n\n"
                "用法:\n"
                "/config time on|off\n"
                "/config format 24h|12h\n"
                "/config location - 设置天气位置"
            )

    async def handle_reload(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /reload 命令 - 重新加载命令菜单"""
        user_id = update.effective_user.id
        
        if not self._check_permission(user_id):
            return
        
        try:
            from telegram import BotCommand
            
            # 重新设置命令菜单
            commands = [
                BotCommand("start", "开始使用日记机器人"),
                BotCommand("help", "显示帮助文档"),
                BotCommand("end", "立即合并今天的日记"),
                BotCommand("config", "配置时间、格式、位置等"),
                BotCommand("reload", "重新加载菜单（开发用）"),
            ]
            
            await context.bot.set_my_commands(commands)
            await update.message.reply_text("✅ 命令菜单已重新加载")
            
        except Exception as e:
            await update.message.reply_text(f"❌ 重新加载失败: {e}")

    async def handle_location(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理用户发送的位置消息"""
        user_id = update.effective_user.id
        
        if not self._check_permission(user_id):
            return
        
        location = update.message.location
        if not location:
            return
        
        lat = location.latitude
        lng = location.longitude
        
        # 导入位置服务
        try:
            from sync.location_service import get_nearest_city
            city = get_nearest_city(lat, lng)
            
            if city:
                # 保存到用户配置
                self.storage.set_user_config(user_id, "weather_location", city)
                
                # 城市中文名映射
                city_names = {
                    'Shanghai': '上海', 'Beijing': '北京', 'Hangzhou': '杭州',
                    'Shenzhen': '深圳', 'Chengdu': '成都', 'Guangzhou': '广州',
                    'Puer': '普洱', 'Hong Kong': '香港',
                }
                city_cn = city_names.get(city, city)
                
                await update.message.reply_text(
                    f"✅ 已保存位置：{city_cn}\n"
                    f"📍 坐标：{lat:.4f}, {lng:.4f}\n\n"
                    f"后续日记将使用{city_cn}的天气数据。",
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                await update.message.reply_text(
                    "⚠️ 未能识别该位置对应的城市。\n"
                    "已保存坐标，将使用默认天气。",
                    reply_markup=ReplyKeyboardRemove()
                )
                self.storage.set_user_config(user_id, "weather_location", f"{lat},{lng}")
                
        except Exception as e:
            logger.exception("处理位置消息失败")
            await update.message.reply_text(
                "⚠️ 位置处理失败，请重试。",
                reply_markup=ReplyKeyboardRemove()
            )
        """处理 /end 命令 - 立即合并今天的日记"""
        user_id = update.effective_user.id

        # 权限检查
        if not self._check_permission(user_id):
            await update.message.reply_text("⚠️ 你没有权限使用这个 bot")
            return

        try:
            await update.message.reply_text("🔄 正在合并今天的日记...")

            # 先上传所有未上传的图片
            today = self.diary_service.get_or_create_today(user_id)
            entries = self.storage.get_entries(today.id)

            if not entries:
                await update.message.reply_text("📭 今天还没有日记内容")
                return

            # 强制合并
            issue_url = await self.scheduler.force_merge_today(user_id)

            if issue_url:
                await update.message.reply_text(f"✅ 日记已合并\n\n🔗 {issue_url}")
            else:
                await update.message.reply_text("⚠️ 合并失败，请检查日志")

        except Exception as e:
            logger.exception("手动合并失败")
            await update.message.reply_text(f"❌ 出错了: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理收到的消息（文本 + 图片）"""
        user_id = update.effective_user.id

        # 权限检查
        if not self._check_permission(user_id):
            logger.warning(f"拒绝未授权用户: {user_id}")
            await update.message.reply_text("⚠️ 你没有权限使用这个 bot")
            return

        # 提取消息内容和图片
        text = update.message.text or update.message.caption or ""
        photos = update.message.photo or []
        message_id = update.message.message_id

        if not text and not photos:
            await update.message.reply_text("🤔 发送点什么吧～")
            return

        try:
            # 解析标签
            tags = self._extract_tags(text)

            # 处理图片上传
            image_refs = []
            if photos:
                image_refs = await self._upload_photos(photos, context)

            # 添加到日记
            self.diary_service.add_message(
                user_id=user_id,
                message_id=message_id,
                content=text,
                images=image_refs,
                tags=tags,
            )

            # 获取今天的日记状态
            journal = self.diary_service.get_or_create_today(user_id)
            entries = self.storage.get_entries(journal.id)

            # 回复用户
            await update.message.reply_text(
                f"✅ 已记录 (#{len(entries)})\n\n"
                f"🏷️ 标签: {', '.join(tags) if tags else '无'}\n"
                f"发送 /end 结束今天的日记"
            )

        except Exception as e:
            logger.exception("处理消息失败")
            await update.message.reply_text(f"❌ 出错了: {e}")

    def _check_permission(self, user_id: int) -> bool:
        """检查用户权限"""
        if not self.config.allowed_user_ids:
            return True
        return user_id in self.config.allowed_user_ids

    def _extract_tags(self, text: str) -> list[str]:
        """从文本中提取 #标签"""
        return extract_tags(text, self.config.journal_label)

    async def _upload_photos(
        self,
        photos: list[PhotoSize],
        context: ContextTypes.DEFAULT_TYPE,
    ) -> list[str]:
        """
        上传图片到 GitHub 仓库，返回图片 URL 列表。
        """
        refs: list[str] = []

        # Telegram 的 message.photo 是同一张图的不同尺寸，取最大尺寸
        largest = max(photos, key=lambda p: p.file_size or 0)

        # 下载图片
        file = await context.bot.get_file(largest.file_id)
        bio = io.BytesIO()
        await file.download_to_memory(bio)
        content = bio.getvalue()

        # 生成文件路径
        now = datetime.now(tz=self.config.timezone)
        date_path = now.strftime("%Y/%m/%d")
        filename = f"photo_{now.strftime('%H%M%S')}_{largest.file_id[-8:]}.jpg"
        file_path = f"{self.config.image_dir}/{date_path}/{filename}"

        # 上传
        result = self.github.upload_file(
            file_path=file_path,
            content=content,
            commit_message=f"Add image {filename}",
        )

        # 获取图片 URL - 使用 GitHub raw URL 格式
        if result and "content" in result:
            # 构建 raw.githubusercontent.com URL
            raw_url = f"https://raw.githubusercontent.com/{self.config.github_owner}/{self.config.github_repo}/{self.config.branch}/{file_path}"
            refs.append(f"![]({raw_url})")

        return refs


# 向后兼容的 MessageHandler 类（单消息处理，不集成日记）
class MessageHandler:
    """Legacy: 单消息处理器（直接创建 Issue）"""

    def __init__(self, config: Config, github: GitHubClient):
        self.config = config
        self.github = github

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理收到的消息（向后兼容）"""
        user_id = update.effective_user.id
        if self.config.allowed_user_ids and user_id not in self.config.allowed_user_ids:
            logger.warning(f"拒绝未授权用户: {user_id}")
            await update.message.reply_text("⚠️ 你没有权限使用这个 bot")
            return

        text = update.message.text or update.message.caption or ""
        photos = update.message.photo or []

        if not text and not photos:
            await update.message.reply_text("🤔 发送点什么吧～")
            return

        try:
            tags = self._extract_tags(text)
            image_refs = []
            if photos:
                image_refs = await self._upload_photos(photos, context)

            issue_title, issue_body = self._build_issue_content(text, image_refs, tags)

            issue = self.github.create_issue(
                title=issue_title,
                body=issue_body,
                labels=tags,
            )

            await update.message.reply_text(
                f"✅ 已记录\n\n"
                f"🔗 {issue['html_url']}\n"
                f"🏷️ 标签: {', '.join(tags) if tags else '无'}"
            )

        except Exception as e:
            logger.exception("处理消息失败")
            await update.message.reply_text(f"❌ 出错了: {e}")

    def _extract_tags(self, text: str) -> list[str]:
        """从文本中提取 #标签"""
        return extract_tags(text, self.config.journal_label)

    async def _upload_photos(
        self,
        photos: list[PhotoSize],
        context: ContextTypes.DEFAULT_TYPE,
    ) -> list[str]:
        """上传图片"""
        refs: list[str] = []
        largest = max(photos, key=lambda p: p.file_size or 0)
        file = await context.bot.get_file(largest.file_id)
        bio = io.BytesIO()
        await file.download_to_memory(bio)
        content = bio.getvalue()

        now = datetime.now(tz=self.config.timezone)
        date_path = now.strftime("%Y/%m/%d")
        filename = f"photo_{now.strftime('%H%M%S')}_{largest.file_id[-8:]}.jpg"
        file_path = f"{self.config.image_dir}/{date_path}/{filename}"

        self.github.upload_file(
            file_path=file_path,
            content=content,
            commit_message=f"Add image {filename}",
        )

        refs.append(f"![](/{file_path.lstrip('/')})")
        return refs

    def _build_issue_content(
        self, text: str, image_refs: list[str], tags: list[str]
    ) -> tuple[str, str]:
        """构建 Issue 标题和正文"""
        title = datetime.now(tz=self.config.timezone).strftime("%Y%m%d")

        body_parts = []
        if text:
            body_parts.append(text)
        if image_refs:
            body_parts.append("\n---\n")
            body_parts.extend(image_refs)

        body = "\n\n".join(body_parts)
        return title, body
