import sys
sys.path.insert(0, '/app')

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import aiohttp
import structlog
from app.config import settings
from app.keyboard.inline import get_main_menu_kb, get_back_kb

router = Router()
logger = structlog.get_logger()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{settings.API_GATEWAY_URL}/users/",
            json={"telegram_id": message.from_user.id, "username": message.from_user.username}
        ) as resp:
            if resp.status == 200:
                user_data = await resp.json()
            else:
                user_data = {"plan": "free", "ai_generations_today": 0}
    
    plan_emoji = "💎" if user_data.get("plan") == "pro" else "🆓"
    
    await message.answer(
        f"👋 Добро пожаловать!\n\n"
        f"Я помогу вам находить проекты на Upwork и создавать отклики с помощью AI.\n\n"
        f"Ваш план: {plan_emoji} {user_data.get('plan', 'free').upper()}\n\n"
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
        "/projects - Лента проектов\n"
        "/filters - Настройка фильтров\n"
        "/ai - AI-генерация откликов\n"
        "/subscription - Управление подпиской\n"
        "/settings - Настройки\n\n"
        "<b>💡 Подсказки:</b>\n"
        "• Используйте фильтры для поиска релевантных проектов\n"
        "• Настройте AI-промпт для персонализированных откликов\n"
        "• Приглашайте друзей и получайте бонусные дни Pro"
    )

@router.callback_query(lambda c: c.data == "main")
async def to_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Главное меню:",
        reply_markup=get_main_menu_kb()
    )
    await callback.answer()
