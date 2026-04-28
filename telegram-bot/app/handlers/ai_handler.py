import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.keyboard.inline import get_ai_kb, get_back_kb, get_main_menu_kb
import structlog

router = Router()
logger = structlog.get_logger()

class AIFSM(StatesGroup):
    main = State()
    generating = State()
    editing_prompt = State()

@router.callback_query(F.data == "ai")
async def show_ai_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AIFSM.main)
    
    await callback.message.edit_text(
        "<b>🤖 AI-генерация откликов</b>\n\n"
        "Функция временно недоступна.\n"
        "Требуется подключение к базе данных.",
        reply_markup=get_back_kb("main")
    )
    await callback.answer()
