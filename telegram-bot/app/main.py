import asyncio
import logging
import sys
sys.path.insert(0, '/app')

import structlog
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from app.config import settings

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

async def main():
    session = AiohttpSession(
        timeout=60,
    )
    
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session
    )
    dp = Dispatcher()
    
    dp.include_router(start.router)
    dp.include_router(auth.router)
    dp.include_router(projects.router)
    dp.include_router(filters.router)
    dp.include_router(ai_handler.router)
    dp.include_router(subscription.router)
    dp.include_router(settings_handler.router)
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logger.warning(f"Could not delete webhook: {e}")
    
    logger.info("bot_started")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
