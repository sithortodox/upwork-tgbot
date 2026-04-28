import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.keyboard.inline import get_back_kb, get_main_menu_kb
from app.services.api_client import APIClient
from app.config import settings
import structlog

router = Router()
logger = structlog.get_logger()
api = APIClient(settings.API_GATEWAY_URL)

class AuthFSM(StatesGroup):
    waiting_code = State()

@router.callback_query(F.data == "auth_start")
async def start_auth(callback: CallbackQuery, state: FSMContext):
    result = await api.get(f"/auth/url/{callback.from_user.id}")
    
    if not result or not result.get("auth_url"):
        await callback.message.edit_text(
            "<b>🔐 Авторизация Upwork</b>\n\n"
            "⚠️ OAuth не настроен. Обратитесь к администратору.",
            reply_markup=get_back_kb("settings")
        )
        await callback.answer()
        return
    
    auth_url = result["auth_url"]
    
    if "client_id=" in auth_url and "client_id=&" in auth_url:
        await callback.message.edit_text(
            "<b>🔐 Авторизация Upwork</b>\n\n"
            "⚠️ Upwork API не настроен.\n\n"
            "Для настройки требуется:\n"
            "1. Создать приложение на upwork.com/developer/api-keys\n"
            "2. Получить Client ID и Client Secret\n"
            "3. Добавить их в конфигурацию бота",
            reply_markup=get_back_kb("settings")
        )
        await callback.answer()
        return
    
    await state.set_state(AuthFSM.waiting_code)
    
    text = "<b>🔐 Авторизация Upwork</b>\n\n"
    text += "1. Нажмите кнопку ниже для перехода на Upwork\n"
    text += "2. Авторизуйтесь и разрешите доступ\n"
    text += "3. После редиректа скопируйте параметр <code>code</code> из URL\n"
    text += "4. Отправьте код сюда\n\n"
    text += "<i>Пример: code=abc123 → отправьте abc123</i>"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Открыть Upwork", url=auth_url)],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="settings")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.message(AuthFSM.waiting_code)
async def process_code(message: Message, state: FSMContext):
    code = message.text.strip()
    
    if len(code) < 10:
        await message.answer("❌ Неверный формат кода. Попробуйте снова.")
        return
    
    result = await api.post(f"/auth/callback/{message.from_user.id}", json={"code": code})
    
    if result and result.get("status") == "success":
        await state.clear()
        await message.answer(
            "✅ Аккаунт Upwork успешно подключен!\n\n"
            "Теперь вы можете использовать все функции бота.",
            reply_markup=get_main_menu_kb()
        )
    else:
        await message.answer("❌ Ошибка авторизации. Проверьте код и попробуйте снова.")

@router.message(F.text.startswith("/auth "))
async def process_deep_link_auth(message: Message, state: FSMContext):
    code = message.text.split(" ")[1] if len(message.text.split()) > 1 else ""
    
    if not code:
        await message.answer("Неверная ссылка")
        return
    
    result = await api.post(f"/auth/callback/{message.from_user.id}", json={"code": code})
    
    if result and result.get("status") == "success":
        await message.answer(
            "✅ Аккаунт Upwork успешно подключен!",
            reply_markup=get_main_menu_kb()
        )
    else:
        await message.answer("❌ Ошибка авторизации")
