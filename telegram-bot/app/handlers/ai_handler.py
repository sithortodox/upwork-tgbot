import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import structlog
from app.config import settings
from app.keyboard.inline import get_ai_kb, get_ai_preview_kb, get_back_kb
from app.services.api_client import APIClient

router = Router()
logger = structlog.get_logger()
api = APIClient(settings.API_GATEWAY_URL, timeout=30)

class AIFSM(StatesGroup):
    main = State()
    generating = State()
    editing_prompt = State()
    preview = State()

@router.callback_query(F.data == "ai")
async def show_ai_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AIFSM.main)
    
    limits = await api.get(f"/ai/{callback.from_user.id}/limits")
    
    if limits:
        daily_limit = limits.get("daily_limit", 5)
        used = limits.get("used_today", 0)
        plan = limits.get("plan", "free")
        
        if plan == "pro":
            left = "∞"
        else:
            left = max(0, daily_limit - used)
    else:
        left = 5
    
    text = f"<b>🤖 AI-генерация откликов</b>\n\n"
    text += f"Осталось генераций сегодня: {left}\n\n"
    text += "Создавайте профессиональные cover letters для проектов!"
    
    await callback.message.edit_text(text, reply_markup=get_ai_kb())
    await callback.answer()

@router.callback_query(F.data == "ai_generate")
async def start_generation(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AIFSM.generating)
    
    text = "<b>✨ Генерация отклика</b>\n\n"
    text += "Перейдите в /projects, выберите проект и нажмите '🤖 Сгенерировать отклик'"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("ai"))
    await callback.answer()

@router.callback_query(F.data.startswith("ai_gen_"))
async def generate_for_project(callback: CallbackQuery, state: FSMContext):
    project_id = callback.data.split("_")[2]
    
    status_msg = await callback.message.answer("⏳ Генерирую отклик...")
    
    result = await api.post(f"/ai/{callback.from_user.id}/generate", json={"project_id": int(project_id)})
    
    if result:
        cover_letter = result.get("cover_letter", "")
        left = result.get("generations_left", 0)
        
        await state.update_data(cover_letter=cover_letter, project_id=project_id)
        await state.set_state(AIFSM.preview)
        
        text = f"<b>📝 Сгенерированный отклик:</b>\n\n"
        text += f"<pre>{cover_letter}</pre>\n\n"
        text += f"Осталось генераций: {left}"
        
        await status_msg.edit_text(text, reply_markup=get_ai_preview_kb())
    else:
        await status_msg.edit_text(
            "❌ Ошибка генерации. Возможно, превышен лимит.",
            reply_markup=get_back_kb("ai")
        )
    
    await callback.answer()

@router.callback_query(F.data == "ai_regenerate")
async def regenerate(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    project_id = data.get("project_id")
    
    if project_id:
        result = await api.post(f"/ai/{callback.from_user.id}/generate", json={"project_id": int(project_id)})
        
        if result:
            cover_letter = result.get("cover_letter", "")
            left = result.get("generations_left", 0)
            
            await state.update_data(cover_letter=cover_letter)
            
            text = f"<b>📝 Новый отклик:</b>\n\n"
            text += f"<pre>{cover_letter}</pre>\n\n"
            text += f"Осталось генераций: {left}"
            
            await callback.message.edit_text(text, reply_markup=get_ai_preview_kb())
    
    await callback.answer()

@router.callback_query(F.data == "ai_copy")
async def copy_response(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cover_letter = data.get("cover_letter", "")
    
    if cover_letter:
        await callback.message.answer(f"📋 Текст для копирования:\n\n{cover_letter}")
    
    await callback.answer()

@router.callback_query(F.data == "ai_prompt")
async def edit_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AIFSM.editing_prompt)
    
    result = await api.get(f"/ai/{callback.from_user.id}/prompt")
    
    current = result.get("prompt", "") if result else ""
    
    text = "<b>📝 Редактирование AI-промпта</b>\n\n"
    if current:
        text += f"Текущий промпт:\n<pre>{current[:300]}...</pre>\n\n"
    text += "Отправьте новый промпт:"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("ai"))
    await callback.answer()

@router.message(AIFSM.editing_prompt)
async def save_prompt(message: Message, state: FSMContext):
    result = await api.put(f"/ai/{message.from_user.id}/prompt", json={"prompt": message.text})
    
    if result:
        await message.answer("✅ Промпт обновлен!")
    else:
        await message.answer("❌ Ошибка сохранения")
    
    await state.set_state(AIFSM.main)

@router.callback_query(F.data == "ai_import")
async def import_style(callback: CallbackQuery, state: FSMContext):
    text = "<b>📥 Импорт стиля написания</b>\n\n"
    text += "Отправьте пример вашего текста (cover letter, письмо и т.д.), чтобы AI мог имитировать ваш стиль."
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("ai"))
    await callback.answer()

@router.message()
async def import_style_text(message: Message, state: FSMContext):
    if len(message.text) < 100:
        return
    
    current_state = await state.get_state()
    if current_state != AIFSM.main:
        return
    
    result = await api.post(f"/ai/{message.from_user.id}/import-style", json={"text": message.text})
    
    if result:
        await message.answer("✅ Стиль успешно импортирован!")
    else:
        await message.answer("❌ Ошибка при импорте")
