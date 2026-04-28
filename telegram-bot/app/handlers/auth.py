import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.keyboard.inline import get_back_kb, get_main_menu_kb
import structlog

router = Router()
logger = structlog.get_logger()

class AuthFSM(StatesGroup):
    waiting_code = State()

@router.callback_query(F.data == "auth_start")
async def start_auth(callback: CallbackQuery, state: FSMContext):
    text = "<b>🔐 Авторизация Upwork</b>\n\n"
    text += "⚠️ Для авторизации требуется настроить Upwork API.\n\n"
    text += "Текущая версия работает в демо-режиме с тестовыми данными."
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("settings"))
    await callback.answer()
