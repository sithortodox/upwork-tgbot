import sys
sys.path.insert(0, '/app')

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Optional

def get_main_menu_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📁 Проекты", callback_data="projects")],
        [InlineKeyboardButton(text="🔍 Фильтры", callback_data="filters")],
        [InlineKeyboardButton(text="🤖 AI-отклики", callback_data="ai")],
        [InlineKeyboardButton(text="💎 Подписка", callback_data="subscription")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_kb(callback_data: str = "main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=callback_data)]
    ])

def get_projects_kb(projects: List[dict] = None, page: int = 0, total: int = 0) -> InlineKeyboardMarkup:
    buttons = []
    
    if projects:
        for i, p in enumerate(projects[:5]):
            project_id = p.get("id") or p.get("external_id")
            buttons.append([
                InlineKeyboardButton(
                    text=f"{i + 1 + page * 5}. {p['title'][:30]}{'...' if len(p['title']) > 30 else ''}",
                    callback_data=f"project_{project_id}"
                )
            ])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"prev_page_{page}"))
    
    nav_buttons.append(InlineKeyboardButton(text="🔄", callback_data="projects_refresh"))
    
    if (page + 1) * 5 < total:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"next_page_{page}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton(text="◀️ Главное меню", callback_data="main")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_project_kb(project_id: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🤖 Сгенерировать отклик", callback_data=f"ai_gen_{project_id}")],
        [InlineKeyboardButton(text="✅ Отметить прочитанным", callback_data="mark_seen")],
        [InlineKeyboardButton(text="◀️ К проектам", callback_data="projects")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_filters_kb(has_filters: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📁 Категории", callback_data="filter_category")],
        [InlineKeyboardButton(text="🔑 Ключевые слова", callback_data="filter_keywords")],
        [InlineKeyboardButton(text="💰 Бюджет", callback_data="filter_budget")],
        [InlineKeyboardButton(text="🤖 AI-редактор", callback_data="filter_ai")],
    ]
    
    if has_filters:
        buttons.append([InlineKeyboardButton(text="🗑 Удалить фильтр", callback_data="filter_delete")])
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_filter_edit_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Сохранить", callback_data="filter_save")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="filters")]
    ])

def get_ai_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="✨ Сгенерировать отклик", callback_data="ai_generate")],
        [InlineKeyboardButton(text="📝 Редактировать промпт", callback_data="ai_prompt")],
        [InlineKeyboardButton(text="📥 Импорт стиля", callback_data="ai_import")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_ai_preview_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🔄 Перегенерировать", callback_data="ai_regenerate")],
        [InlineKeyboardButton(text="📋 Копировать", callback_data="ai_copy")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="ai")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_subscription_kb(current_plan: str = "free") -> InlineKeyboardMarkup:
    buttons = []
    
    if current_plan == "free":
        buttons.append([InlineKeyboardButton(text="⭐ Оплатить Stars", callback_data="sub_stars")])
        buttons.append([InlineKeyboardButton(text="💳 ЮKassa", callback_data="sub_yookassa")])
    
    buttons.append([InlineKeyboardButton(text="👥 Реферальная программа", callback_data="sub_referral")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_settings_kb(has_session: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="settings_notifications")],
        [InlineKeyboardButton(text="🔐 Прокси", callback_data="settings_proxy")],
    ]
    
    if has_session:
        buttons.append([InlineKeyboardButton(text="❌ Отвязать аккаунт", callback_data="settings_unlink")])
    else:
        buttons.append([InlineKeyboardButton(text="🔗 Подключить Upwork", callback_data="auth_start")])
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
