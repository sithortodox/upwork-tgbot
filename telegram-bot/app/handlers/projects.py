import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.keyboard.inline import get_projects_kb, get_project_kb, get_back_kb
import structlog

router = Router()
logger = structlog.get_logger()

class ProjectsFSM(StatesGroup):
    viewing = State()
    viewing_project = State()

MOCK_PROJECTS = [
    {
        "id": 1,
        "external_id": "12345",
        "title": "Python Developer for Web Scraping",
        "description": "Need a Python developer to build a web scraping solution for e-commerce data collection. Experience with BeautifulSoup and Selenium required.",
        "budget_min": 500,
        "budget_max": 1000,
        "category": "Web Development",
        "url": "https://www.upwork.com/jobs/12345",
        "is_new": True
    },
    {
        "id": 2,
        "external_id": "12346",
        "title": "React Native Mobile App Development",
        "description": "Looking for an experienced React Native developer to build a cross-platform mobile application for iOS and Android.",
        "budget_min": 2000,
        "budget_max": 5000,
        "category": "Mobile Development",
        "url": "https://www.upwork.com/jobs/12346",
        "is_new": True
    },
    {
        "id": 3,
        "external_id": "12347",
        "title": "Logo Design for Tech Startup",
        "description": "Need a modern, minimalist logo design for a tech startup. Must provide vector files and multiple revisions.",
        "budget_min": 200,
        "budget_max": 500,
        "category": "Design",
        "url": "https://www.upwork.com/jobs/12347",
        "is_new": False
    }
]

@router.callback_query(F.data == "projects")
async def show_projects(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProjectsFSM.viewing)
    await state.update_data(projects=MOCK_PROJECTS, page=0, total=len(MOCK_PROJECTS))
    
    text = "<b>📁 Лента проектов</b>\n\n"
    for i, p in enumerate(MOCK_PROJECTS):
        budget = f" ${p['budget_min']}-{p['budget_max']}"
        new_badge = "🆕 " if p['is_new'] else ""
        text += f"{i + 1}. {new_badge}{p['title']}{budget}\n"
    
    text += f"\n📄 Страница 1 из 1"
    
    kb = get_projects_kb(MOCK_PROJECTS, 0, len(MOCK_PROJECTS))
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("project_"))
async def show_project_detail(callback: CallbackQuery, state: FSMContext):
    project_id = int(callback.data.split("_")[1])
    
    project = next((p for p in MOCK_PROJECTS if p["id"] == project_id), None)
    if not project:
        await callback.answer("Проект не найден")
        return
    
    await state.set_state(ProjectsFSM.viewing_project)
    await state.update_data(current_project=project)
    
    budget = f"${project['budget_min']} - ${project['budget_max']}"
    
    text = f"""<b>{project['title']}</b>

📝 {project['description']}

💰 Бюджет: {budget}
📁 Категория: {project['category']}

👉 <a href="{project['url']}">Открыть на Upwork</a>"""
    
    await callback.message.edit_text(
        text,
        reply_markup=get_project_kb(str(project_id)),
        disable_web_page_preview=True
    )
    await callback.answer()

@router.callback_query(F.data == "projects_refresh")
async def refresh_projects(callback: CallbackQuery, state: FSMContext):
    await show_projects(callback, state)

@router.callback_query(F.data == "mark_seen")
async def mark_seen(callback: CallbackQuery, state: FSMContext):
    await callback.answer("✅ Проект отмечен как просмотренный")
