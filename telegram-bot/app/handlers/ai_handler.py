import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiohttp
from app.config import settings
from app.keyboard.inline import get_ai_kb, get_back_kb, get_main_menu_kb
import structlog

router = Router()
logger = structlog.get_logger()

class AIFSM(StatesGroup):
    main = State()
    generating = State()
    editing_prompt = State()
    importing_style = State()
    preview = State()

@router.callback_query(F.data == "ai")
async def show_ai_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AIFSM.main)
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{settings.API_GATEWAY_URL}/ai/{callback.from_user.id}/limits"
        ) as resp:
            if resp.status == 200:
                limits = await resp.json()
            else:
                limits = {"daily_limit": settings.FREE_DAILY_AI_LIMIT, "used_today": 0, "plan": "free"}
    
    left = limits.get("daily_limit", 5) - limits.get("used_today", 0)
    if limits.get("plan") == "pro":
        left = "∞"
    
    text = f"<b>🤖 AI-генерация откликов</b>\n\n"
    text += f"Осталось генераций сегодня: {left}\n\n"
    text += "Создавайте профессиональные cover letters для проектов!"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_ai_kb()
    )
    await callback.answer()

@router.callback_query(F.data == "ai_generate")
async def start_generation(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AIFSM.generating)
    
    text = "<b>✨ Генерация отклика</b>\n\n"
    text += "Выберите проект для генерации отклика.\n\n"
    text += "Отправьте ID проекта или перейдите в /projects"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("ai"))
    await callback.answer()

@router.message(AIFSM.generating)
async def process_generation(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите числовой ID проекта")
        return
    
    project_id = int(message.text)
    await state.update_data(generating_project_id=project_id)
    
    status_msg = await message.answer("⏳ Генерирую отклик...")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{settings.API_GATEWAY_URL}/ai/{message.from_user.id}/generate",
            json={"project_id": project_id}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                cover_letter = data.get("cover_letter", "")
                left = data.get("generations_left", 0)
                
                await state.update_data(
                    cover_letter=cover_letter,
                    project_id=project_id
                )
                await state.set_state(AIFSM.preview)
                
                text = f"<b>📝 Сгенерированный отклик:</b>\n\n"
                text += f"<pre>{cover_letter}</pre>\n\n"
                text += f"Осталось генераций: {left}"
                
                await status_msg.edit_text(
                    text,
                    reply_markup=get_ai_preview_kb()
                )
            elif resp.status == 403:
                await status_msg.edit_text(
                    "❌ Лимит генераций на сегодня исчерпан.\n"
                    "Оформите Pro-подписку для безлимита!",
                    reply_markup=get_back_kb("ai")
                )
                await state.set_state(AIFSM.main)
            else:
                await status_msg.edit_text(
                    "❌ Ошибка генерации. Проверьте ID проекта.",
                    reply_markup=get_back_kb("ai")
                )
                await state.set_state(AIFSM.main)

@router.callback_query(F.data == "ai_regenerate")
async def regenerate(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    project_id = data.get("project_id")
    
    if project_id:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{settings.API_GATEWAY_URL}/ai/{callback.from_user.id}/generate",
                json={"project_id": project_id}
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    cover_letter = result.get("cover_letter", "")
                    
                    await state.update_data(cover_letter=cover_letter)
                    
                    text = f"<b>📝 Новый отклик:</b>\n\n"
                    text += f"<pre>{cover_letter}</pre>\n\n"
                    text += f"Осталось генераций: {result.get('generations_left', 0)}"
                    
                    await callback.message.edit_text(
                        text,
                        reply_markup=get_ai_preview_kb()
                    )
    
    await callback.answer()

@router.callback_query(F.data == "ai_copy")
async def copy_response(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cover_letter = data.get("cover_letter", "")
    
    if cover_letter:
        await callback.message.answer(
            f"📋 Скопируйте текст:\n\n{cover_letter}",
            reply_markup=get_main_menu_kb()
        )
    
    await callback.answer()

@router.callback_query(F.data == "ai_prompt")
async def edit_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AIFSM.editing_prompt)
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{settings.API_GATEWAY_URL}/ai/{callback.from_user.id}/prompt"
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                current_prompt = data.get("prompt", "")
            else:
                current_prompt = ""
    
    text = "<b>📝 Редактирование AI-промпта</b>\n\n"
    text += f"Текущий промпт:\n<pre>{current_prompt[:500]}...</pre>\n\n"
    text += "Отправьте новый промпт:"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("ai"))
    await callback.answer()

@router.message(AIFSM.editing_prompt)
async def save_prompt(message: Message, state: FSMContext):
    async with aiohttp.ClientSession() as session:
        async with session.put(
            f"{settings.API_GATEWAY_URL}/ai/{message.from_user.id}/prompt",
            json={"prompt": message.text}
        ) as resp:
            if resp.status == 200:
                await message.answer("✅ Промпт обновлен!")
            else:
                await message.answer("❌ Ошибка при сохранении")
    
    await state.set_state(AIFSM.main)

@router.callback_query(F.data == "ai_import")
async def import_style(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AIFSM.importing_style)
    
    text = "<b>📥 Импорт стиля написания</b>\n\n"
    text += "Отправьте пример вашего текста (cover letter, письмо и т.д.), "
    text += "чтобы AI мог имитировать ваш стиль."
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("ai"))
    await callback.answer()

@router.message(AIFSM.importing_style)
async def process_style_import(message: Message, state: FSMContext):
    if len(message.text) < 100:
        await message.answer("Текст слишком короткий. Отправьте хотя бы 100 символов.")
        return
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{settings.API_GATEWAY_URL}/ai/{message.from_user.id}/import-style",
            json={"text": message.text}
        ) as resp:
            if resp.status == 200:
                await message.answer("✅ Стиль успешно импортирован!")
            else:
                await message.answer("❌ Ошибка при импорте")
    
    await state.set_state(AIFSM.main)

def get_ai_preview_kb():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Перегенерировать", callback_data="ai_regenerate")],
        [InlineKeyboardButton(text="📋 Копировать", callback_data="ai_copy")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="ai")]
    ])
