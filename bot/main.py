"""
Telegram Bot 入口

使用 Long Polling 方式运行，适合在本地 Mac mini 上 7x24 运行。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from telegram import BotCommand
from telegram.ext import ApplicationBuilder

from .config import Config
from .github_client import GitHubClient
from .handlers import BotHandlers

# 配置日志
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Bot 命令菜单
BOT_COMMANDS = [
    BotCommand("start", "开始使用日记机器人"),
    BotCommand("help", "显示帮助文档"),
    BotCommand("end", "立即合并今天的日记"),
    BotCommand("config", "配置时间、格式、位置等"),
    BotCommand("reload", "重新加载菜单（开发用）"),
]


def main(env_path: str | Path | None = None) -> None:
    """主函数"""
    # 加载配置
    config = Config.from_env(env_path=env_path)
    logger.info(f"配置加载完成: {config.github_owner}/{config.github_repo}")

    # 初始化 GitHub 客户端
    github_client = GitHubClient(config)

    # 初始化处理器（包含日记服务和调度器）
    bot_handlers = BotHandlers(config, github_client)

    # 构建 Telegram Bot Application
    app = ApplicationBuilder().token(config.telegram_token).build()

    # 注册所有处理器
    for handler in bot_handlers.get_handlers():
        app.add_handler(handler)

    # 启动后设置命令菜单（使用 post_init 回调）
    async def setup_commands(app):
        try:
            await app.bot.set_my_commands(BOT_COMMANDS)
            logger.info("✅ Bot 命令菜单已设置")
        except Exception as e:
            logger.warning(f"⚠️ 设置命令菜单失败: {e}")

    app.post_init = setup_commands

    # 启动调度器（在异步上下文中）
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        # 如果已经在运行（如被 nb-cli 调用），创建任务
        loop.create_task(bot_handlers.start_scheduler())
    else:
        loop.run_until_complete(bot_handlers.start_scheduler())

    # 启动 Bot（Long Polling）
    logger.info("🚀 Bot 启动中...")
    logger.info("命令: /start, /help, /end, /config")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
