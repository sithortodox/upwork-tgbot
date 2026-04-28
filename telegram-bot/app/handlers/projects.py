import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.keyboard.inline import get_projects_kb, get_back_kb, get_main_menu_kb
import structlog

router = Router()
logger = structlog.get_logger()

class ProjectsFSM(StatesGroup):
    viewing = State()
    viewing_project = State()

@router.callback_query(F.data == "projects")
async def show_projects(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProjectsFSM.viewing)
    
    await callback.message.edit_text(
        "<b>📁 Лента проектов</b>\n\n"
        "📭 Проекты временно недоступны.\n"
        "Требуется подключение к базе данных.",
        reply_markup=get_back_kb("main")
    )
    await callback.answer()

@router.callback_query(F.data == "projects_refresh")
async def refresh_projects(callback: CallbackQuery, state: FSMContext):
    await show_projects(callback, state)
