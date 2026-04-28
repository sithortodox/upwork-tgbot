import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiohttp
from app.config import settings
from app.keyboard.inline import get_back_kb, get_main_menu_kb
import structlog

router = Router()
logger = structlog.get_logger()

class AuthFSM(StatesGroup):
    waiting_code = State()

@router.message(F.text.startswith("/start "))
async def process_referral_or_auth(message: Message, state: FSMContext):
    param = message.text.split(" ")[1] if len(message.text.split()) > 1 else ""
    
    if len(param) == 8 and param.isalnum():
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{settings.API_GATEWAY_URL}/subscription/{message.from_user.id}/apply-referral/{param}"
            ) as resp:
                if resp.status == 200:
                    await message.answer(
                        "🎉 Вы использовали реферальный код!\n"
                        "Вы и ваш друг получили бонус."
                    )
                elif resp.status == 400:
                    await message.answer("Вы уже использовали реферальный код ранее")
                else:
                    await message.answer("Недействительный реферальный код")
    
    await message.answer(
        "👋 Добро пожаловать!",
        reply_markup=get_main_menu_kb()
    )

@router.callback_query(F.data == "auth_start")
async def start_auth(callback: CallbackQuery, state: FSMContext):
    auth_url = (
        f"https://www.upwork.com/ab/account-security/oauth2/authorize"
        f"?client_id={settings.UPWORK_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri=https://t.me/your_bot"
    )
    
    text = "<b>🔐 Авторизация Upwork</b>\n\n"
    text += "1. Нажмите кнопку ниже\n"
    text += "2. Авторизуйтесь на Upwork\n"
    text += "3. Скопируйте код из URL после редиректа\n"
    text += "4. Отправьте код сюда\n\n"
    text += "Формат URL после авторизации:\n"
    text += "<code>https://t.me/bot?code=YOUR_CODE</code>"
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Открыть Upwork", url=auth_url)],
        [InlineKeyboardButton(text="✅ Я отправил код", callback_data="auth_enter_code")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "auth_enter_code")
async def enter_auth_code(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AuthFSM.waiting_code)
    
    await callback.message.edit_text(
        "<b>📝 Введите код авторизации</b>\n\n"
        "Отправьте код из URL после авторизации на Upwork",
        reply_markup=get_back_kb("settings")
    )
    await callback.answer()

@router.message(AuthFSM.waiting_code)
async def process_auth_code(message: Message, state: FSMContext):
    code = message.text.strip()
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{settings.API_GATEWAY_URL}/auth/callback/{message.from_user.id}",
            json={"code": code}
        ) as resp:
            if resp.status == 200:
                await message.answer(
                    "✅ Авторизация успешна!\n\n"
                    "Теперь вы можете использовать все функции бота.",
                    reply_markup=get_main_menu_kb()
                )
                await state.clear()
            else:
                error = await resp.json() if resp.content_type == "application/json" else {}
                await message.answer(
                    f"❌ Ошибка авторизации\n\n"
                    f"{error.get('detail', 'Попробуйте снова')}"
                )
