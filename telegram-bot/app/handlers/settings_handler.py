import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiohttp
from app.config import settings
from app.keyboard.inline import get_settings_kb, get_back_kb, get_main_menu_kb
import structlog

router = Router()
logger = structlog.get_logger()

class SettingsFSM(StatesGroup):
    main = State()
    editing_proxy = State()
    editing_notifications = State()

@router.callback_query(F.data == "settings")
async def show_settings(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsFSM.main)
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{settings.API_GATEWAY_URL}/users/status/{callback.from_user.id}"
        ) as resp:
            if resp.status == 200:
                user_status = await resp.json()
            else:
                user_status = {"exists": False, "has_session": False, "plan": "free"}
        
        async with session.get(
            f"{settings.API_GATEWAY_URL}/subscription/{callback.from_user.id}/notifications"
        ) as resp:
            if resp.status == 200:
                notif_settings = await resp.json()
            else:
                notif_settings = {"enabled": True, "schedule": "immediate"}
    
    session_status = "✅ Подключен" if user_status.get("has_session") else "❌ Не подключен"
    notif_status = "✅ Включены" if notif_settings.get("enabled") else "❌ Выключены"
    
    schedule_names = {
        "immediate": "Сразу",
        "hourly": "Раз в час",
        "daily": "Раз в день"
    }
    schedule_name = schedule_names.get(notif_settings.get("schedule"), "Сразу")
    
    text = "<b>⚙️ Настройки</b>\n\n"
    text += f"Аккаунт Upwork: {session_status}\n"
    text += f"Уведомления: {notif_status} ({schedule_name})\n"
    text += f"План: {user_status.get('plan', 'free').upper()}"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_settings_kb(user_status.get("has_session"))
    )
    await callback.answer()

@router.callback_query(F.data == "settings_proxy")
async def edit_proxy(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsFSM.editing_proxy)
    
    text = "<b>🔐 Настройка прокси</b>\n\n"
    text += "Отправьте адрес прокси в формате:\n"
    text += "<code>http://user:pass@host:port</code>\n\n"
    text += "Или отправьте '-' чтобы отключить прокси"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("settings"))
    await callback.answer()

@router.message(SettingsFSM.editing_proxy)
async def save_proxy(message: Message, state: FSMContext):
    proxy = message.text.strip() if message.text.strip() != "-" else None
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{settings.API_GATEWAY_URL}/auth/proxy/{message.from_user.id}",
            json={"proxy_url": proxy}
        ) as resp:
            if resp.status == 200:
                await message.answer("✅ Прокси обновлен")
            else:
                await message.answer("❌ Ошибка при сохранении")
    
    await state.set_state(SettingsFSM.main)

@router.callback_query(F.data == "settings_notifications")
async def edit_notifications(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsFSM.editing_notifications)
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{settings.API_GATEWAY_URL}/subscription/{callback.from_user.id}/notifications"
        ) as resp:
            if resp.status == 200:
                settings_data = await resp.json()
            else:
                settings_data = {"enabled": True, "schedule": "immediate"}
    
    text = "<b>🔔 Настройка уведомлений</b>\n\n"
    text += f"Статус: {'✅ Включены' if settings_data.get('enabled') else '❌ Выключены'}\n"
    text += f"Режим: {settings_data.get('schedule')}\n\n"
    text += "Выберите режим:"
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔔 Включить" if not settings_data.get("enabled") else "🔕 Выключить",
            callback_data=f"notif_toggle_{0 if settings_data.get('enabled') else 1}"
        )],
        [InlineKeyboardButton(text="⚡ Сразу", callback_data="notif_immediate")],
        [InlineKeyboardButton(text="🕐 Раз в час", callback_data="notif_hourly")],
        [InlineKeyboardButton(text="📅 Раз в день", callback_data="notif_daily")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="settings")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("notif_toggle_"))
async def toggle_notifications(callback: CallbackQuery, state: FSMContext):
    enabled = callback.data.split("_")[2] == "1"
    
    async with aiohttp.ClientSession() as session:
        async with session.put(
            f"{settings.API_GATEWAY_URL}/subscription/{callback.from_user.id}/notifications",
            json={"enabled": enabled}
        ) as resp:
            pass
    
    await edit_notifications(callback, state)

@router.callback_query(F.data == "notif_immediate")
async def set_notif_immediate(callback: CallbackQuery, state: FSMContext):
    await update_notification_schedule(callback.from_user.id, "immediate")
    await callback.answer("Режим обновлен")
    await edit_notifications(callback, state)

@router.callback_query(F.data == "notif_hourly")
async def set_notif_hourly(callback: CallbackQuery, state: FSMContext):
    await update_notification_schedule(callback.from_user.id, "hourly")
    await callback.answer("Режим обновлен")
    await edit_notifications(callback, state)

@router.callback_query(F.data == "notif_daily")
async def set_notif_daily(callback: CallbackQuery, state: FSMContext):
    await update_notification_schedule(callback.from_user.id, "daily")
    await callback.answer("Режив обновлен")
    await edit_notifications(callback, state)

@router.callback_query(F.data == "settings_unlink")
async def unlink_account(callback: CallbackQuery, state: FSMContext):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, отвязать", callback_data="unlink_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="settings")]
    ])
    
    await callback.message.edit_text(
        "<b>⚠️ Отвязка аккаунта</b>\n\n"
        "Вы уверены, что хотите отвязать аккаунт Upwork?\n"
        "Вам придется пройти авторизацию заново.",
        reply_markup=kb
    )
    await callback.answer()

@router.callback_query(F.data == "unlink_confirm")
async def confirm_unlink(callback: CallbackQuery, state: FSMContext):
    async with aiohttp.ClientSession() as session:
        async with session.delete(
            f"{settings.API_GATEWAY_URL}/auth/{callback.from_user.id}"
        ) as resp:
            if resp.status == 200:
                await callback.message.edit_text(
                    "✅ Аккаунт отвязан",
                    reply_markup=get_main_menu_kb()
                )
            else:
                await callback.answer("Ошибка")
    
    await state.clear()

async def update_notification_schedule(user_id: int, schedule: str):
    async with aiohttp.ClientSession() as session:
        await session.put(
            f"{settings.API_GATEWAY_URL}/subscription/{user_id}/notifications",
            json={"schedule": schedule}
        )
