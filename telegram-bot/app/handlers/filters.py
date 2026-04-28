import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.keyboard.inline import get_filters_kb, get_back_kb
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
    
    text = "<b>🔍 Ваши фильтры</b>\n\n"
    text += "<b>Основной фильтр</b>\n"
    text += "📁 Категории: Web Development, Mobile Development\n"
    text += "✅ Включить: python, react, javascript\n"
    text += "❌ Исключить: (нет)\n"
    text += "💰 Бюджет: $100 - $5000\n\n"
    text += "Статус: ✅ Активен"
    
    await callback.message.edit_text(text, reply_markup=get_filters_kb(True))
    await callback.answer()

@router.callback_query(F.data == "filter_category")
async def edit_category(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterFSM.editing_category)
    
    text = "<b>📁 Редактирование категорий</b>\n\n"
    text += "Текущие: Web Development, Mobile Development\n\n"
    text += "Введите категории через запятую:"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("filters"))
    await callback.answer()

@router.callback_query(F.data == "filter_keywords")
async def edit_keywords(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterFSM.editing_keywords)
    
    text = "<b>🔑 Редактирование ключевых слов</b>\n\n"
    text += "Включить: python, react, javascript\n"
    text += "Исключить: (нет)\n\n"
    text += "Отправьте слова в формате:\n"
    text += "+python, +react (включить)\n"
    text += "-scam, -test (исключить)"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("filters"))
    await callback.answer()

@router.callback_query(F.data == "filter_budget")
async def edit_budget(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterFSM.editing_budget)
    
    text = "<b>💰 Редактирование бюджета</b>\n\n"
    text += "Текущий: $100 - $5000\n\n"
    text += "Введите бюджет в формате: мин-макс\n"
    text += "Пример: 100-500"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("filters"))
    await callback.answer()

@router.callback_query(F.data == "filter_ai")
async def ai_edit_filter(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterFSM.editing_budget)
    
    text = "<b>🤖 AI-редактор фильтров</b>\n\n"
    text += "Опишите словами, какие проекты вы ищете.\n"
    text += "Пример: 'Ищу проекты по Python разработке с бюджетом от $500'"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("filters"))
    await callback.answer()

@router.callback_query(F.data == "filter_delete")
async def delete_filter(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✅ Фильтр удален",
        reply_markup=get_back_kb("main")
    )
    await callback.answer()

@router.message(FilterFSM.editing_category)
async def save_category(message: Message, state: FSMContext):
    await message.answer("✅ Категории обновлены")
    await state.set_state(FilterFSM.main)

@router.message(FilterFSM.editing_keywords)
async def save_keywords(message: Message, state: FSMContext):
    await message.answer("✅ Ключевые слова обновлены")
    await state.set_state(FilterFSM.main)

@router.message(FilterFSM.editing_budget)
async def save_budget(message: Message, state: FSMContext):
    await message.answer("✅ Бюджет обновлен")
    await state.set_state(FilterFSM.main)
