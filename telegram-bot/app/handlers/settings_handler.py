import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.keyboard.inline import get_settings_kb, get_back_kb, get_main_menu_kb
import structlog

router = Router()
logger = structlog.get_logger()

class SettingsFSM(StatesGroup):
    main = State()
    editing_proxy = State()
    editing_notifications = State()

@router.callback_query(F.data == "settings")
async def show_settings(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsFSM.main)
    
    await callback.message.edit_text(
        "<b>⚙️ Настройки</b>\n\n"
        "Настройки временно недоступны.\n"
        "Требуется подключение к базе данных.",
        reply_markup=get_back_kb("main")
    )
    await callback.answer()
