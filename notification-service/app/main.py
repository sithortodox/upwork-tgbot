import asyncio
import sys
sys.path.insert(0, '/app')

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.services.notification import NotificationService
from shared.database import init_db
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

scheduler = AsyncIOScheduler()

async def main():
    await init_db()
    
    scheduler.add_job(
        NotificationService.check_and_send_notifications,
        IntervalTrigger(minutes=1),
        id="check_notifications",
        replace_existing=True
    )
    
    scheduler.add_job(
        NotificationService.send_hourly_digests,
        IntervalTrigger(hours=1),
        id="hourly_digest",
        replace_existing=True
    )
    
    scheduler.add_job(
        NotificationService.send_daily_digests,
        IntervalTrigger(hours=24),
        id="daily_digest",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("notification_service_started")
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()
        logger.info("notification_service_stopped")

if __name__ == "__main__":
    asyncio.run(main())
