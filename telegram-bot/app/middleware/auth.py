from aiogram.types import Message
from structlog import get_logger

logger = get_logger()

class AuthMiddleware:
    async def __call__(self, handler, event, data):
        if isinstance(event, Message):
            user_id = event.from_user.id
            data["user_id"] = user_id
            logger.info("user_request", user_id=user_id)
        return await handler(event, data)
