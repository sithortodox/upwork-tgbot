import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.keyboard.inline import get_settings_kb, get_back_kb
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
    
    text = "<b>⚙️ Настройки</b>\n\n"
    text += "Аккаунт Upwork: ❌ Не подключен\n"
    text += "Уведомления: ✅ Включены (Сразу)\n"
    text += "План: FREE"
    
    await callback.message.edit_text(text, reply_markup=get_settings_kb(False))
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

@router.callback_query(F.data == "settings_notifications")
async def edit_notifications(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsFSM.editing_notifications)
    
    text = "<b>🔔 Настройка уведомлений</b>\n\n"
    text += "Статус: ✅ Включены\n"
    text += "Режим: Сразу\n\n"
    text += "Выберите режим:"
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔕 Выключить", callback_data="notif_off")],
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
    
    if mode == "off":
        msg = "🔕 Уведомления выключены"
    else:
        msg = f"✅ Режим обновлен: {mode}"
    
    await callback.answer(msg)
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
    from app.keyboard.inline import get_main_menu_kb
    await callback.message.edit_text(
        "✅ Аккаунт отвязан",
        reply_markup=get_main_menu_kb()
    )
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "auth_start")
async def start_auth(callback: CallbackQuery, state: FSMContext):
    text = "<b>🔐 Авторизация Upwork</b>\n\n"
    text += "⚠️ Требуется настройка Upwork API\n\n"
    text += "Для полноценной работы необходимо:\n"
    text += "1. Создать приложение на Upwork\n"
    text += "2. Получить Client ID и Secret\n"
    text += "3. Настроить OAuth 2.0"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("settings"))
    await callback.answer()

@router.message(SettingsFSM.editing_proxy)
async def save_proxy(message: Message, state: FSMContext):
    await message.answer("✅ Прокси обновлен")
    await state.set_state(SettingsFSM.main)
