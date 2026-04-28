import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.keyboard.inline import get_filters_kb, get_back_kb, get_main_menu_kb
import structlog

router = Router()
logger = structlog.get_logger()

class FilterFSM(StatesGroup):
    main = State()
    editing_category = State()
    editing_keywords = State()
    editing_budget = State()

@router.callback_query(F.data == "filters")
async def show_filters(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterFSM.main)
    
    await callback.message.edit_text(
        "<b>🔍 Фильтры</b>\n\n"
        "Настройка фильтров временно недоступна.\n"
        "Требуется подключение к базе данных.",
        reply_markup=get_back_kb("main")
    )
    await callback.answer()
