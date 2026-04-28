import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiohttp
from app.config import settings
from app.keyboard.inline import get_filters_kb, get_filter_edit_kb, get_back_kb, get_main_menu_kb
import structlog

router = Router()
logger = structlog.get_logger()

class FilterFSM(StatesGroup):
    main = State()
    editing_category = State()
    editing_keywords = State()
    editing_budget = State()
    ai_editing = State()

@router.callback_query(F.data == "filters")
async def show_filters(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterFSM.main)
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{settings.API_GATEWAY_URL}/filters/{callback.from_user.id}"
        ) as resp:
            if resp.status == 200:
                filters = await resp.json()
            else:
                filters = []
    
    if filters:
        f = filters[0]
        text = f"<b>🔍 Ваши фильтры</b>\n\n"
        text += f"<b>{f.get('name', 'Основной')}</b>\n"
        
        if f.get("categories"):
            text += f"📁 Категории: {', '.join(f['categories'])}\n"
        if f.get("keywords_include"):
            text += f"✅ Включить: {', '.join(f['keywords_include'])}\n"
        if f.get("keywords_exclude"):
            text += f"❌ Исключить: {', '.join(f['keywords_exclude'])}\n"
        if f.get("budget_min") or f.get("budget_max"):
            budget = f"${f.get('budget_min', 0):.0f} - ${f.get('budget_max', '∞')}"
            text += f"💰 Бюджет: {budget}\n"
        
        text += f"\nСтатус: {'✅ Активен' if f.get('is_active') else '❌ Неактивен'}"
        
        await state.update_data(current_filter=f)
    else:
        text = "<b>🔍 Фильтры</b>\n\nУ вас пока нет настроенных фильтров."
    
    await callback.message.edit_text(
        text,
        reply_markup=get_filters_kb(bool(filters))
    )
    await callback.answer()

@router.callback_query(F.data == "filter_category")
async def edit_category(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterFSM.editing_category)
    
    data = await state.get_data()
    current = data.get("current_filter", {})
    categories = current.get("categories", [])
    
    text = "<b>📁 Редактирование категорий</b>\n\n"
    text += f"Текущие: {', '.join(categories) if categories else 'Не указаны'}\n\n"
    text += "Введите категории через запятую:"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("filters"))
    await callback.answer()

@router.message(FilterFSM.editing_category)
async def save_category(message: Message, state: FSMContext):
    categories = [c.strip() for c in message.text.split(",") if c.strip()]
    
    await update_filter(message.from_user.id, {"categories": categories})
    
    await message.answer("✅ Категории обновлены")
    await state.set_state(FilterFSM.main)

@router.callback_query(F.data == "filter_keywords")
async def edit_keywords(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterFSM.editing_keywords)
    
    data = await state.get_data()
    current = data.get("current_filter", {})
    
    text = "<b>🔑 Редактирование ключевых слов</b>\n\n"
    text += f"Включить: {', '.join(current.get('keywords_include', [])) or 'Не указаны'}\n"
    text += f"Исключить: {', '.join(current.get('keywords_exclude', [])) or 'Не указаны'}\n\n"
    text += "Отправьте слова в формате:\n"
    text += "+python, +django (включить)\n"
    text += "-scam, -test (исключить)"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("filters"))
    await callback.answer()

@router.message(FilterFSM.editing_keywords)
async def save_keywords(message: Message, state: FSMContext):
    include = []
    exclude = []
    
    for word in message.text.split(","):
        word = word.strip()
        if word.startswith("+"):
            include.append(word[1:].strip())
        elif word.startswith("-"):
            exclude.append(word[1:].strip())
        elif word:
            include.append(word)
    
    await update_filter(message.from_user.id, {
        "keywords_include": include,
        "keywords_exclude": exclude
    })
    
    await message.answer("✅ Ключевые слова обновлены")
    await state.set_state(FilterFSM.main)

@router.callback_query(F.data == "filter_budget")
async def edit_budget(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterFSM.editing_budget)
    
    data = await state.get_data()
    current = data.get("current_filter", {})
    
    text = "<b>💰 Редактирование бюджета</b>\n\n"
    text += f"Мин: ${current.get('budget_min', 'Не указан')}\n"
    text += f"Макс: ${current.get('budget_max', 'Не указан')}\n\n"
    text += "Введите бюджет в формате: мин-макс\n"
    text += "Пример: 100-500 или 100-"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("filters"))
    await callback.answer()

@router.message(FilterFSM.editing_budget)
async def save_budget(message: Message, state: FSMContext):
    parts = message.text.replace(" ", "").split("-")
    
    budget_min = None
    budget_max = None
    
    if len(parts) >= 1 and parts[0]:
        try:
            budget_min = float(parts[0])
        except:
            pass
    
    if len(parts) >= 2 and parts[1]:
        try:
            budget_max = float(parts[1])
        except:
            pass
    
    await update_filter(message.from_user.id, {
        "budget_min": budget_min,
        "budget_max": budget_max
    })
    
    await message.answer("✅ Бюджет обновлен")
    await state.set_state(FilterFSM.main)

@router.callback_query(F.data == "filter_ai")
async def ai_edit_filter(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterFSM.ai_editing)
    
    text = "<b>🤖 AI-редактор фильтров</b>\n\n"
    text += "Опишите словами, какие проекты вы ищете.\n"
    text += "Пример: 'Ищу проекты по Python разработке с бюджетом от $500'"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("filters"))
    await callback.answer()

@router.message(FilterFSM.ai_editing)
async def process_ai_edit(message: Message, state: FSMContext):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{settings.API_GATEWAY_URL}/filters/{message.from_user.id}/ai-edit",
            json={"command": message.text}
        ) as resp:
            if resp.status == 200:
                await message.answer(
                    "✅ Фильтры обновлены с помощью AI!\n"
                    "Проверьте настройки: /filters"
                )
            else:
                await message.answer("❌ Ошибка при обработке запроса")
    
    await state.set_state(FilterFSM.main)

@router.callback_query(F.data == "filter_delete")
async def delete_filter(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current = data.get("current_filter", {})
    filter_id = current.get("id")
    
    if filter_id:
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"{settings.API_GATEWAY_URL}/filters/{callback.from_user.id}/{filter_id}"
            ) as resp:
                pass
    
    await callback.message.edit_text(
        "✅ Фильтр удален",
        reply_markup=get_main_menu_kb()
    )
    await callback.answer()

async def update_filter(user_id: int, data: dict):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{settings.API_GATEWAY_URL}/filters/{user_id}"
        ) as resp:
            if resp.status == 200:
                filters = await resp.json()
                if filters:
                    filter_id = filters[0]["id"]
                    await session.put(
                        f"{settings.API_GATEWAY_URL}/filters/{user_id}/{filter_id}",
                        json=data
                    )
                    return
        
        await session.post(
            f"{settings.API_GATEWAY_URL}/filters/{user_id}",
            json=data
        )
