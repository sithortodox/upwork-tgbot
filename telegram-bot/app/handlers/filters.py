import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import structlog
from app.config import settings
from app.keyboard.inline import get_filters_kb, get_back_kb
from app.services.api_client import APIClient
from shared.utils import parse_list_field

router = Router()
logger = structlog.get_logger()
api = APIClient(settings.API_GATEWAY_URL)

class FilterFSM(StatesGroup):
    main = State()
    editing_category = State()
    editing_keywords = State()
    editing_budget = State()

@router.callback_query(F.data == "filters")
async def show_filters(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterFSM.main)
    
    filters = await api.get(f"/filters/{callback.from_user.id}")
    
    if filters and len(filters) > 0:
        f = filters[0]
        text = f"<b>🔍 Ваши фильтры</b>\n\n"
        text += f"<b>{f.get('name', 'Основной')}</b>\n"
        
        cats = parse_list_field(f.get('categories', '[]'))
        if cats:
            text += f"📁 Категории: {', '.join(cats)}\n"
        
        kw_inc = parse_list_field(f.get('keywords_include', '[]'))
        if kw_inc:
            text += f"✅ Включить: {', '.join(kw_inc)}\n"
        
        kw_exc = parse_list_field(f.get('keywords_exclude', '[]'))
        if kw_exc:
            text += f"❌ Исключить: {', '.join(kw_exc)}\n"
        
        if f.get('budget_min') or f.get('budget_max'):
            bmin = f.get('budget_min', 0)
            bmax = f.get('budget_max', '∞')
            text += f"💰 Бюджет: ${bmin} - ${bmax}\n"
        
        text += f"\nСтатус: {'✅ Активен' if f.get('is_active') else '❌ Неактивен'}"
        
        await state.update_data(current_filter=f)
    else:
        text = "<b>🔍 Фильтры</b>\n\nУ вас пока нет настроенных фильтров."
    
    has_filters = filters and len(filters) > 0
    await callback.message.edit_text(text, reply_markup=get_filters_kb(has_filters))
    await callback.answer()

@router.callback_query(F.data == "filter_category")
async def edit_category(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterFSM.editing_category)
    
    data = await state.get_data()
    current = data.get("current_filter", {})
    cats = parse_list_field(current.get('categories', '[]'))
    
    text = "<b>📁 Редактирование категорий</b>\n\n"
    text += f"Текущие: {', '.join(cats) if cats else 'Не указаны'}\n\n"
    text += "Введите категории через запятую:"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("filters"))
    await callback.answer()

@router.message(FilterFSM.editing_category)
async def save_category(message: Message, state: FSMContext):
    categories = [c.strip() for c in message.text.split(",") if c.strip()]
    
    data = await state.get_data()
    filter_id = data.get("current_filter", {}).get("id")
    
    if filter_id:
        await api.put(f"/filters/{message.from_user.id}/{filter_id}", json={"categories": categories})
    else:
        await api.post(f"/filters/{message.from_user.id}", json={"categories": categories})
    
    await message.answer("✅ Категории обновлены")
    await state.set_state(FilterFSM.main)

@router.callback_query(F.data == "filter_keywords")
async def edit_keywords(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterFSM.editing_keywords)
    
    data = await state.get_data()
    current = data.get("current_filter", {})
    
    kw_inc = parse_list_field(current.get('keywords_include', '[]'))
    kw_exc = parse_list_field(current.get('keywords_exclude', '[]'))
    
    text = "<b>🔑 Редактирование ключевых слов</b>\n\n"
    text += f"Включить: {', '.join(kw_inc) if kw_inc else 'Не указаны'}\n"
    text += f"Исключить: {', '.join(kw_exc) if kw_exc else 'Не указаны'}\n\n"
    text += "Отправьте слова в формате:\n+python, +django (включить)\n-scam, -test (исключить)"
    
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
    
    data = await state.get_data()
    filter_id = data.get("current_filter", {}).get("id")
    
    payload = {"keywords_include": include, "keywords_exclude": exclude}
    
    if filter_id:
        await api.put(f"/filters/{message.from_user.id}/{filter_id}", json=payload)
    else:
        await api.post(f"/filters/{message.from_user.id}", json=payload)
    
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
    text += "Введите бюджет в формате: мин-макс\nПример: 100-500 или 100-"
    
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
    
    data = await state.get_data()
    filter_id = data.get("current_filter", {}).get("id")
    
    payload = {"budget_min": budget_min, "budget_max": budget_max}
    
    if filter_id:
        await api.put(f"/filters/{message.from_user.id}/{filter_id}", json=payload)
    else:
        await api.post(f"/filters/{message.from_user.id}", json=payload)
    
    await message.answer("✅ Бюджет обновлен")
    await state.set_state(FilterFSM.main)

@router.callback_query(F.data == "filter_delete")
async def delete_filter(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    filter_id = data.get("current_filter", {}).get("id")
    
    if filter_id:
        await api.delete(f"/filters/{callback.from_user.id}/{filter_id}")
    
    from app.keyboard.inline import get_main_menu_kb
    await callback.message.edit_text("✅ Фильтр удален", reply_markup=get_main_menu_kb())
    await callback.answer()
