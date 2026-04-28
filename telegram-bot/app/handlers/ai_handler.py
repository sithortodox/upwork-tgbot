import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.keyboard.inline import get_ai_kb, get_ai_preview_kb, get_back_kb
import structlog

router = Router()
logger = structlog.get_logger()

class AIFSM(StatesGroup):
    main = State()
    generating = State()
    editing_prompt = State()
    preview = State()

@router.callback_query(F.data == "ai")
async def show_ai_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AIFSM.main)
    
    text = "<b>🤖 AI-генерация откликов</b>\n\n"
    text += "Осталось генераций сегодня: 5\n\n"
    text += "Создавайте профессиональные cover letters для проектов!"
    
    await callback.message.edit_text(text, reply_markup=get_ai_kb())
    await callback.answer()

@router.callback_query(F.data == "ai_generate")
async def start_generation(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AIFSM.generating)
    
    text = "<b>✨ Генерация отклика</b>\n\n"
    text += "Выберите проект для генерации отклика.\n\n"
    text += "Перейдите в /projects, выберите проект и нажмите 'Сгенерировать отклик'"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("ai"))
    await callback.answer()

@router.callback_query(F.data.startswith("ai_gen_"))
async def generate_for_project(callback: CallbackQuery, state: FSMContext):
    project_id = callback.data.split("_")[2]
    
    await state.set_state(AIFSM.preview)
    
    cover_letter = """Hi there!

I'm an experienced Python developer with 5+ years of expertise in web scraping and data collection. I've successfully completed similar projects using BeautifulSoup, Selenium, and Scrapy.

For your e-commerce data scraping project, I can:
- Build a robust scraping solution with anti-detection measures
- Set up automated data extraction and storage
- Provide clean, structured data in your preferred format
- Ensure scalability for multiple websites

I'm available to start immediately and can deliver within your timeline. Let's discuss your requirements in detail.

Best regards,
[Your Name]"""
    
    await state.update_data(cover_letter=cover_letter, project_id=project_id)
    
    text = f"<b>📝 Сгенерированный отклик:</b>\n\n"
    text += f"<pre>{cover_letter}</pre>\n\n"
    text += f"Осталось генераций: 4"
    
    await callback.message.edit_text(text, reply_markup=get_ai_preview_kb())
    await callback.answer()

@router.callback_query(F.data == "ai_regenerate")
async def regenerate(callback: CallbackQuery, state: FSMContext):
    cover_letter = """Hello!

I specialize in Python web scraping and would love to help with your project. My approach includes:

✅ Custom scraping scripts tailored to your needs
✅ Handling dynamic content and JavaScript
✅ Proxy rotation and rate limiting
✅ Data validation and cleaning

I've worked on 50+ similar projects and understand the challenges of e-commerce data collection.

Ready to start? Let's chat!

Best,
[Your Name]"""
    
    await state.update_data(cover_letter=cover_letter)
    
    text = f"<b>📝 Новый отклик:</b>\n\n"
    text += f"<pre>{cover_letter}</pre>\n\n"
    text += f"Осталось генераций: 3"
    
    await callback.message.edit_text(text, reply_markup=get_ai_preview_kb())
    await callback.answer()

@router.callback_query(F.data == "ai_copy")
async def copy_response(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cover_letter = data.get("cover_letter", "")
    
    if cover_letter:
        await callback.message.answer(
            f"📋 Текст для копирования:\n\n{cover_letter}"
        )
    
    await callback.answer()

@router.callback_query(F.data == "ai_prompt")
async def edit_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AIFSM.editing_prompt)
    
    text = "<b>📝 Редактирование AI-промпта</b>\n\n"
    text += "Текущий промпт используется для генерации откликов.\n\n"
    text += "Отправьте новый промпт:"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("ai"))
    await callback.answer()

@router.callback_query(F.data == "ai_import")
async def import_style(callback: CallbackQuery, state: FSMContext):
    text = "<b>📥 Импорт стиля написания</b>\n\n"
    text += "Отправьте пример вашего текста (cover letter, письмо и т.д.), "
    text += "чтобы AI мог имитировать ваш стиль."
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("ai"))
    await callback.answer()

@router.message(AIFSM.editing_prompt)
async def save_prompt(message: Message, state: FSMContext):
    await message.answer("✅ Промпт обновлен!")
    await state.set_state(AIFSM.main)
