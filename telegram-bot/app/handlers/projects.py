import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiohttp
from app.config import settings
from app.keyboard.inline import get_projects_kb, get_project_kb, get_back_kb, get_main_menu_kb
import structlog

router = Router()
logger = structlog.get_logger()

class ProjectsFSM(StatesGroup):
    viewing = State()
    viewing_project = State()
    generating = State()

@router.callback_query(F.data == "projects")
async def show_projects(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProjectsFSM.viewing)
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{settings.API_GATEWAY_URL}/projects/{callback.from_user.id}",
            params={"limit": 5, "offset": 0}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                projects = data.get("projects", [])
                total = data.get("total", 0)
            else:
                projects = []
                total = 0
    
    if not projects:
        await callback.message.edit_text(
            "📭 Проекты не найдены.\n\n"
            "Попробуйте изменить фильтры или проверьте позже.",
            reply_markup=get_back_kb("main")
        )
        await callback.answer()
        return
    
    await state.update_data(projects=projects, page=0, total=total)
    
    await show_projects_page(callback, projects, 0, total)

def format_project_short(project: dict, index: int) -> str:
    budget = ""
    if project.get("budget_min") and project.get("budget_max"):
        budget = f" ${project['budget_min']:.0f}-${project['budget_max']:.0f}"
    elif project.get("budget_min"):
        budget = f" от ${project['budget_min']:.0f}"
    
    new_badge = "🆕 " if project.get("is_new") else ""
    
    return f"{index + 1}. {new_badge}{project['title']}{budget}"

async def show_projects_page(callback: CallbackQuery, projects: list, page: int, total: int):
    text = f"<b>📁 Лента проектов</b>\n\n"
    
    for i, p in enumerate(projects):
        text += format_project_short(p, i + page * 5) + "\n"
    
    text += f"\n📄 Страница {page + 1} из {max(1, (total + 4) // 5)}"
    
    kb = get_projects_kb(projects, page, total)
    
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except:
        await callback.message.answer(text, reply_markup=kb)

@router.callback_query(F.data.startswith("project_"))
async def show_project_detail(callback: CallbackQuery, state: FSMContext):
    project_id = callback.data.split("_")[1]
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{settings.API_GATEWAY_URL}/projects/{callback.from_user.id}/project/{project_id}"
        ) as resp:
            if resp.status == 200:
                project = await resp.json()
            else:
                await callback.answer("Проект не найден")
                return
    
    await state.set_state(ProjectsFSM.viewing_project)
    await state.update_data(current_project=project)
    
    budget = "Не указан"
    if project.get("budget_min") and project.get("budget_max"):
        budget = f"${project['budget_min']:.0f} - ${project['budget_max']:.0f}"
    elif project.get("budget_min"):
        budget = f"От ${project['budget_min']:.0f}"
    elif project.get("budget_max"):
        budget = f"До ${project['budget_max']:.0f}"
    
    text = f"""<b>{project['title']}</b>

📝 {project['description'][:1000]}{'...' if len(project['description']) > 1000 else ''}

💰 Бюджет: {budget}
📁 Категория: {project.get('category', 'Не указана')}
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=get_project_kb(project_id),
        disable_web_page_preview=True
    )
    await callback.answer()

@router.callback_query(F.data == "projects_refresh")
async def refresh_projects(callback: CallbackQuery, state: FSMContext):
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{settings.API_GATEWAY_URL}/projects/refresh") as resp:
            pass
    
    await show_projects(callback, state)

@router.callback_query(F.data.startswith("prev_page_"))
async def prev_page(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = max(0, data.get("page", 0) - 1)
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{settings.API_GATEWAY_URL}/projects/{callback.from_user.id}",
            params={"limit": 5, "offset": page * 5}
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                projects = result.get("projects", [])
    
    await state.update_data(projects=projects, page=page)
    await show_projects_page(callback, projects, page, data.get("total", 0))

@router.callback_query(F.data.startswith("next_page_"))
async def next_page(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get("page", 0) + 1
    total = data.get("total", 0)
    
    if page * 5 >= total:
        await callback.answer("Это последняя страница")
        return
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{settings.API_GATEWAY_URL}/projects/{callback.from_user.id}",
            params={"limit": 5, "offset": page * 5}
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                projects = result.get("projects", [])
    
    await state.update_data(projects=projects, page=page)
    await show_projects_page(callback, projects, page, total)

@router.callback_query(F.data == "mark_seen")
async def mark_seen(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    project = data.get("current_project", {})
    project_id = project.get("id")
    
    if project_id:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{settings.API_GATEWAY_URL}/projects/{callback.from_user.id}/seen/{project_id}"
            )
    
    await callback.answer("Проект отмечен как просмотренный")
