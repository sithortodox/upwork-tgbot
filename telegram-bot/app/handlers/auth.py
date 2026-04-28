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
    waiting_email = State()
    waiting_password = State()
    waiting_2fa = State()
    waiting_cookies = State()

@router.callback_query(F.data == "auth_start")
async def start_auth(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔐 Ввести логин/пароль", callback_data="auth_credentials")],
        [InlineKeyboardButton(text="🍪 Вставить cookies", callback_data="auth_cookies")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="settings")]
    ])
    
    await callback.message.edit_text(
        "<b>🔐 Подключение Upwork</b>\n\n"
        "Выберите способ авторизации:\n\n"
        "• <b>Логин/пароль</b> — бот автоматически войдёт\n"
        "• <b>Cookies</b> — скопируйте cookies из браузера",
        reply_markup=kb
    )
    await callback.answer()

@router.callback_query(F.data == "auth_credentials")
async def ask_email(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AuthFSM.waiting_email)
    
    await callback.message.edit_text(
        "<b>📧 Введите email</b>\n\n"
        "Введите email, который вы используете для входа на Upwork:",
        reply_markup=get_back_kb("settings")
    )
    await callback.answer()

@router.message(AuthFSM.waiting_email)
async def process_email(message: Message, state: FSMContext):
    email = message.text.strip()
    
    if "@" not in email or "." not in email:
        await message.answer("❌ Неверный формат email. Попробуйте снова:")
        return
    
    await state.update_data(email=email)
    await state.set_state(AuthFSM.waiting_password)
    
    await message.answer(
        "<b>🔑 Введите пароль</b>\n\n"
        "⚠️ Пароль будет зашифрован и безопасно сохранён.\n"
        "Отправьте пароль от Upwork:",
        reply_markup=get_back_kb("settings")
    )

@router.message(AuthFSM.waiting_password)
async def process_password(message: Message, state: FSMContext):
    password = message.text.strip()
    await message.delete()
    
    await state.update_data(password=password)
    await state.set_state(AuthFSM.waiting_2fa)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="auth_skip_2fa")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="settings")]
    ])
    
    await message.answer(
        "<b>🔐 Двухфакторная аутентификация</b>\n\n"
        "Если у вас включён Google Authenticator (TOTP), введите секретный ключ.\n"
        "Иначе нажмите \"Пропустить\":",
        reply_markup=kb
    )

@router.callback_query(F.data == "auth_skip_2fa")
async def skip_2fa(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    result = await api.post(
        f"/auth/credentials/{callback.from_user.id}",
        json={
            "email": data.get("email"),
            "password": data.get("password")
        }
    )
    
    await state.clear()
    
    if result and result.get("status") == "success":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Войти сейчас", callback_data="auth_do_login")],
            [InlineKeyboardButton(text="✅ Готово", callback_data="main_menu")]
        ])
        await callback.message.edit_text(
            "✅ Данные сохранены!\n\n"
            "Нажмите \"Войти сейчас\" для авторизации или бот автоматически выполнит вход при следующем поиске проектов.",
            reply_markup=kb
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка сохранения данных",
            reply_markup=get_back_kb("settings")
        )
    
    await callback.answer()

@router.callback_query(F.data == "auth_do_login")
async def do_login(callback: CallbackQuery):
    await callback.message.edit_text("⏳ Выполняю вход на Upwork... Это может занять до 30 секунд.")
    
    result = await api.post(f"/auth/login/{callback.from_user.id}")
    
    if result and result.get("status") == "success":
        await callback.message.edit_text(
            "✅ Вход выполнен успешно!\n\n"
            "Аккаунт Upwork подключен.",
            reply_markup=get_main_menu_kb()
        )
    else:
        error_msg = result.get("message", "Неизвестная ошибка") if result else "Ошибка соединения"
        await callback.message.edit_text(
            f"❌ Ошибка входа: {error_msg}\n\n"
            "Проверьте логин/пароль или используйте cookies.",
            reply_markup=get_back_kb("settings")
        )
    
    await callback.answer()

@router.message(AuthFSM.waiting_2fa)
async def process_2fa(message: Message, state: FSMContext):
    totp_secret = message.text.strip()
    await message.delete()
    
    data = await state.get_data()
    
    result = await api.post(
        f"/auth/credentials/{message.from_user.id}",
        json={
            "email": data.get("email"),
            "password": data.get("password"),
            "totp_secret": totp_secret
        }
    )
    
    await state.clear()
    
    if result and result.get("status") == "success":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Войти сейчас", callback_data="auth_do_login")],
            [InlineKeyboardButton(text="✅ Готово", callback_data="main_menu")]
        ])
        await message.answer(
            "✅ Данные сохранены!\n\n"
            "Нажмите \"Войти сейчас\" для авторизации или бот автоматически выполнит вход при следующем поиске проектов.",
            reply_markup=kb
        )
    else:
        await message.answer("❌ Ошибка сохранения данных")

@router.callback_query(F.data == "auth_cookies")
async def ask_cookies(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AuthFSM.waiting_cookies)
    
    await callback.message.edit_text(
        "<b>🍪 Вставка cookies</b>\n\n"
        "<b>Как получить cookies:</b>\n"
        "1. Откройте upwork.com в браузере\n"
        "2. Войдите в свой аккаунт\n"
        "3. Откройте Developer Tools (F12)\n"
        "4. Перейдите в Console\n"
        "5. Выполните: <code>JSON.stringify(document.cookie.split(';').map(c=>({name:c.split('=')[0].trim(),value:c.split('=')[1],domain:'.upwork.com',path:'/'})))</code>\n"
        "6. Скопируйте результат и отправьте сюда",
        reply_markup=get_back_kb("settings")
    )
    await callback.answer()

@router.message(AuthFSM.waiting_cookies)
async def process_cookies(message: Message, state: FSMContext):
    cookies = message.text.strip()
    
    result = await api.post(
        f"/auth/cookies/{message.from_user.id}",
        json={"cookies": cookies}
    )
    
    await state.clear()
    
    if result and result.get("status") == "success":
        await message.answer(
            "✅ Cookies сохранены!\n\n"
            "Аккаунт Upwork успешно подключен.",
            reply_markup=get_main_menu_kb()
        )
    else:
        await message.answer("❌ Ошибка сохранения cookies")
