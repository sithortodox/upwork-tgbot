import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiohttp
from app.config import settings
from app.keyboard.inline import get_subscription_kb, get_back_kb, get_main_menu_kb
import structlog

router = Router()
logger = structlog.get_logger()

class SubscriptionFSM(StatesGroup):
    main = State()
    payment = State()
    referral = State()

@router.callback_query(F.data == "subscription")
async def show_subscription(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SubscriptionFSM.main)
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{settings.API_GATEWAY_URL}/subscription/{callback.from_user.id}/status"
        ) as resp:
            if resp.status == 200:
                status = await resp.json()
            else:
                status = {"plan": "free", "days_left": 0}
    
    plan_emoji = "💎" if status.get("plan") == "pro" else "🆓"
    days = status.get("days_left", 0)
    
    text = f"<b>💎 Подписка</b>\n\n"
    text += f"Ваш план: {plan_emoji} {status.get('plan', 'free').upper()}\n"
    
    if status.get("plan") == "pro" and days > 0:
        text += f"Осталось дней: {days}\n\n"
    elif status.get("plan") == "pro":
        text += f"Бессрочно\n\n"
    else:
        text += "\n"
    
    text += "<b>Free:</b> 5 генераций/день, базовые фильтры\n"
    text += "<b>Pro:</b> безлимит AI, расширенные фильтры, приоритет\n\n"
    text += "💰 <b>Цена: 499₽/мес</b>"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_subscription_kb(status.get("plan"))
    )
    await callback.answer()

@router.callback_query(F.data == "sub_stars")
async def pay_stars(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SubscriptionFSM.payment)
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{settings.API_GATEWAY_URL}/subscription/{callback.from_user.id}/pay",
            json={"method": "stars", "days": 30}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                payment_id = data.get("payment_id")
            else:
                await callback.answer("Ошибка создания платежа")
                return
    
    text = "<b>⭐ Оплата через Telegram Stars</b>\n\n"
    text += "Нажмите кнопку ниже для оплаты.\n\n"
    text += "30 дней Pro: ⭐ 50 Stars"
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Оплатить", callback_data=f"stars_pay_{payment_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="subscription")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("stars_pay_"))
async def process_stars_payment(callback: CallbackQuery, state: FSMContext):
    payment_id = callback.data.split("_")[2]
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{settings.API_GATEWAY_URL}/subscription/{callback.from_user.id}/confirm/{payment_id}"
        ) as resp:
            if resp.status == 200:
                await callback.message.edit_text(
                    "✅ Подписка активирована!\n\n"
                    "💎 Pro активен на 30 дней",
                    reply_markup=get_main_menu_kb()
                )
            else:
                await callback.answer("Ошибка активации")
    
    await state.set_state(SubscriptionFSM.main)

@router.callback_query(F.data == "sub_yookassa")
async def pay_yookassa(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SubscriptionFSM.payment)
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{settings.API_GATEWAY_URL}/subscription/{callback.from_user.id}/pay",
            json={"method": "yookassa", "days": 30}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                payment_url = data.get("payment_url")
            else:
                await callback.answer("Ошибка создания платежа")
                return
    
    if payment_url:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment_url)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="subscription")]
        ])
        
        await callback.message.edit_text(
            "<b>💳 Оплата через ЮKassa</b>\n\n"
            "Нажмите кнопку для перехода на страницу оплаты",
            reply_markup=kb
        )
    else:
        await callback.answer("Ошибка получения ссылки")
    
    await callback.answer()

@router.callback_query(F.data == "sub_referral")
async def show_referral(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SubscriptionFSM.referral)
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{settings.API_GATEWAY_URL}/subscription/{callback.from_user.id}/referral"
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
            else:
                data = {"referral_code": "ERROR", "invited_count": 0, "earned_days": 0}
    
    code = data.get("referral_code", "")
    invited = data.get("invited_count", 0)
    earned = data.get("earned_days", 0)
    
    bot_username = "your_bot"
    referral_link = f"https://t.me/{bot_username}?start={code}"
    
    text = f"<b>👥 Реферальная программа</b>\n\n"
    text += f"Ваша реферальная ссылка:\n<code>{referral_link}</code>\n\n"
    text += f"Приглашено: {invited} человек\n"
    text += f"Заработано дней Pro: {earned}\n\n"
    text += "🎁 За каждого приглашенного — 7 дней Pro!"
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться", switch_inline_query=referral_link)],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="subscription")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()
