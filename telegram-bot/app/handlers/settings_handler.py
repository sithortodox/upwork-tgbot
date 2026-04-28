import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import structlog
from app.config import settings
from app.keyboard.inline import get_settings_kb, get_back_kb, get_main_menu_kb
from app.services.api_client import APIClient

router = Router()
logger = structlog.get_logger()
api = APIClient(settings.API_GATEWAY_URL)

class SettingsFSM(StatesGroup):
    main = State()
    editing_proxy = State()
    editing_notifications = State()

@router.callback_query(F.data == "settings")
async def show_settings(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsFSM.main)
    
    user_status = await api.get(f"/users/status/{callback.from_user.id}")
    notif_settings = await api.get(f"/subscription/{callback.from_user.id}/notifications")
    
    has_session = False
    if user_status:
        has_session = user_status.get("has_session", False)
    
    enabled = True
    schedule = "immediate"
    if notif_settings:
        enabled = notif_settings.get("enabled", True)
        schedule = notif_settings.get("schedule", "immediate")
    
    session_status = "✅ Подключен" if has_session else "❌ Не подключен"
    notif_status = "✅ Включены" if enabled else "❌ Выключены"
    
    schedule_names = {"immediate": "Сразу", "hourly": "Раз в час", "daily": "Раз в день"}
    schedule_name = schedule_names.get(schedule, "Сразу")
    
    text = "<b>⚙️ Настройки</b>\n\n"
    text += f"Аккаунт Upwork: {session_status}\n"
    text += f"Уведомления: {notif_status} ({schedule_name})\n"
    
    await callback.message.edit_text(text, reply_markup=get_settings_kb(has_session))
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
    
    result = await api.post(f"/auth/proxy/{message.from_user.id}", json={"proxy_url": proxy})
    
    if result:
        await message.answer("✅ Прокси обновлен")
    else:
        await message.answer("❌ Ошибка при сохранении")
    
    await state.set_state(SettingsFSM.main)

@router.callback_query(F.data == "settings_notifications")
async def edit_notifications(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsFSM.editing_notifications)
    
    notif = await api.get(f"/subscription/{callback.from_user.id}/notifications")
    
    enabled = notif.get("enabled", True) if notif else True
    schedule = notif.get("schedule", "immediate") if notif else "immediate"
    
    text = "<b>🔔 Настройка уведомлений</b>\n\n"
    text += f"Статус: {'✅ Включены' if enabled else '❌ Выключены'}\n"
    text += f"Режим: {schedule}\n\n"
    text += "Выберите режим:"
    
    toggle_text = "🔕 Выключить" if enabled else "🔔 Включить"
    toggle_cb = "notif_off" if enabled else "notif_on"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=toggle_cb)],
        [InlineKeyboardButton(text="⚡ Сразу", callback_data="notif_immediate")],
        [InlineKeyboardButton(text="🕐 Раз в час", callback_data="notif_hourly")],
        [InlineKeyboardButton(text="📅 Раз в день", callback_data="notif_daily")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="settings")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("notif_"))
async def set_notification_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split("_")[1]
    
    if mode == "on":
        await api.put(f"/subscription/{callback.from_user.id}/notifications", json={"enabled": True})
        await callback.answer("✅ Уведомления включены")
    elif mode == "off":
        await api.put(f"/subscription/{callback.from_user.id}/notifications", json={"enabled": False})
        await callback.answer("🔕 Уведомления выключены")
    else:
        await api.put(f"/subscription/{callback.from_user.id}/notifications", json={"schedule": mode})
        await callback.answer(f"✅ Режим: {mode}")
    
    await edit_notifications(callback, state)

@router.callback_query(F.data == "settings_unlink")
async def unlink_account(callback: CallbackQuery, state: FSMContext):
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
    result = await api.delete(f"/auth/{callback.from_user.id}")
    
    if result:
        await callback.message.edit_text("✅ Аккаунт отвязан", reply_markup=get_main_menu_kb())
    else:
        await callback.answer("Ошибка")
    
    await state.clear()

@router.callback_query(F.data == "auth_start")
async def start_auth(callback: CallbackQuery, state: FSMContext):
    text = "<b>🔐 Авторизация Upwork</b>\n\n"
    text += "⚠️ Для полной авторизации требуется настройка Upwork API.\n\n"
    text += "Требуется:\n"
    text += "1. Создать приложение на Upwork\n"
    text += "2. Получить Client ID и Secret\n"
    text += "3. Добавить в конфигурацию"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("settings"))
    await callback.answer()
