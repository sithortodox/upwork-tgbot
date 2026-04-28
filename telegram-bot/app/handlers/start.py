import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import structlog
from app.keyboard.inline import get_main_menu_kb, get_back_kb

router = Router()
logger = structlog.get_logger()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    logger.info("start_command", user_id=message.from_user.id, username=message.from_user.username)
    
    await message.answer(
        "👋 Добро пожаловать!\n\n"
        "Я помогу вам находить проекты на Upwork и создавать отклики с помощью AI.\n\n"
        "Ваш план: 🆓 FREE\n\n"
        "Выберите действие:",
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
        "• Проекты обновляются автоматически"
    )

@router.callback_query(F.data == "main")
async def to_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Главное меню:",
        reply_markup=get_main_menu_kb()
    )
    await callback.answer()
