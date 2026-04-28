import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import structlog
from app.config import settings
from app.keyboard.inline import get_main_menu_kb, get_back_kb
from app.services.api_client import APIClient

router = Router()
logger = structlog.get_logger()
api = APIClient(settings.API_GATEWAY_URL)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    logger.info("start_command", user_id=message.from_user.id, username=message.from_user.username)
    
    user_data = await api.post("/users/", json={
        "telegram_id": message.from_user.id,
        "username": message.from_user.username
    })
    
    if user_data:
        plan = user_data.get("plan", "free")
        plan_emoji = "💎" if plan == "pro" else "🆓"
        days_left = user_data.get("plan_days_left", 0)
        
        status = f"Ваш план: {plan_emoji} {plan.upper()}"
        if plan == "pro" and days_left > 0:
            status += f" ({days_left} дн.)"
    else:
        status = "Ваш план: 🆓 FREE"
    
    await message.answer(
        f"👋 Добро пожаловать!\n\n"
        f"Я помогу вам находить проекты на Upwork и создавать отклики с помощью AI.\n\n"
        f"{status}\n\n"
        f"Выберите действие:",
        reply_markup=get_main_menu_kb()
    )

@router.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_menu_kb()
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "<b>📖 Справка по командам</b>\n\n"
        "/start - Начать работу\n"
        "/menu - Главное меню\n"
        "/help - Справка\n\n"
        "<b>💡 Подсказки:</b>\n"
        "• Используйте кнопки для навигации\n"
        "• Проекты обновляются автоматически\n"
        "• AI помогает создавать профессиональные отклики"
    )

@router.callback_query(F.data == "main")
async def to_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Главное меню:",
        reply_markup=get_main_menu_kb()
    )
    await callback.answer()
