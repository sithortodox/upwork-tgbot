import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import structlog
from app.config import settings
from app.keyboard.inline import get_subscription_kb, get_back_kb, get_main_menu_kb
from app.services.api_client import APIClient

router = Router()
logger = structlog.get_logger()
api = APIClient(settings.API_GATEWAY_URL)

class SubscriptionFSM(StatesGroup):
    main = State()
    payment = State()
    referral = State()

@router.callback_query(F.data == "subscription")
async def show_subscription(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SubscriptionFSM.main)
    
    status = await api.get(f"/subscription/{callback.from_user.id}/status")
    
    if status:
        plan = status.get("plan", "free")
        days_left = status.get("days_left", 0)
        used = status.get("generations_today", 0)
        limit = status.get("daily_limit", 5)
    else:
        plan = "free"
        days_left = 0
        used = 0
        limit = 5
    
    plan_emoji = "💎" if plan == "pro" else "🆓"
    
    text = f"<b>💎 Подписка</b>\n\n"
    text += f"Ваш план: {plan_emoji} {plan.upper()}\n"
    
    if plan == "pro" and days_left > 0:
        text += f"Осталось дней: {days_left}\n"
    
    text += f"Использовано сегодня: {used}/{limit if plan == 'free' else '∞'}\n\n"
    text += "<b>Free:</b> 5 генераций/день, базовые фильтры\n"
    text += "<b>Pro:</b> безлимит AI, расширенные фильтры, приоритет\n\n"
    text += "💰 <b>Цена: 499₽/мес</b>"
    
    await callback.message.edit_text(text, reply_markup=get_subscription_kb(plan))
    await callback.answer()

@router.callback_query(F.data == "sub_stars")
async def pay_stars(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SubscriptionFSM.payment)
    
    result = await api.post(f"/subscription/{callback.from_user.id}/pay", json={"method": "stars", "days": 30})
    
    if result:
        payment_id = result.get("payment_id")
    else:
        await callback.answer("Ошибка создания платежа")
        return
    
    text = "<b>⭐ Оплата через Telegram Stars</b>\n\n"
    text += "30 дней Pro: ⭐ 50 Stars"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Оплатить", callback_data=f"stars_pay_{payment_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="subscription")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("stars_pay_"))
async def process_stars_payment(callback: CallbackQuery, state: FSMContext):
    payment_id = callback.data.split("_")[2]
    
    result = await api.post(f"/subscription/{callback.from_user.id}/confirm/{payment_id}")
    
    if result:
        await callback.message.edit_text(
            "✅ Подписка активирована!\n\n💎 Pro активен на 30 дней",
            reply_markup=get_main_menu_kb()
        )
    else:
        await callback.answer("Ошибка активации")
    
    await state.set_state(SubscriptionFSM.main)

@router.callback_query(F.data == "sub_yookassa")
async def pay_yookassa(callback: CallbackQuery, state: FSMContext):
    result = await api.post(f"/subscription/{callback.from_user.id}/pay", json={"method": "yookassa", "days": 30})
    
    if result:
        payment_url = result.get("payment_url")
        
        if payment_url:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment_url)],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="subscription")]
            ])
            
            await callback.message.edit_text(
                "<b>💳 Оплата через ЮKassa</b>\n\nНажмите кнопку для перехода на страницу оплаты",
                reply_markup=kb
            )
        else:
            await callback.answer("Ошибка получения ссылки")
    else:
        await callback.answer("Ошибка создания платежа")
    
    await state.set_state(SubscriptionFSM.payment)
    await callback.answer()

@router.callback_query(F.data == "sub_referral")
async def show_referral(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SubscriptionFSM.referral)
    
    result = await api.get(f"/subscription/{callback.from_user.id}/referral")
    
    if result:
        code = result.get("referral_code", "")
        invited = result.get("invited_count", 0)
        earned = result.get("earned_days", 0)
    else:
        code = "ERROR"
        invited = 0
        earned = 0
    
    bot_username = "test_upwork_test_bot"
    referral_link = f"https://t.me/{bot_username}?start={code}"
    
    text = f"<b>👥 Реферальная программа</b>\n\n"
    text += f"Ваша реферальная ссылка:\n<code>{referral_link}</code>\n\n"
    text += f"Приглашено: {invited} человек\n"
    text += f"Заработано дней Pro: {earned}\n\n"
    text += "🎁 За каждого приглашенного — 7 дней Pro!"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться", switch_inline_query=referral_link)],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="subscription")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.message(F.text.startswith("/start "))
async def process_referral_or_auth(message: Message, state: FSMContext):
    param = message.text.split(" ")[1] if len(message.text.split()) > 1 else ""
    
    if len(param) == 8 and param.isalnum():
        result = await api.post(f"/subscription/{message.from_user.id}/apply-referral/{param}")
        
        if result:
            await message.answer("🎉 Вы использовали реферальный код!\nВы и ваш друг получили бонус.")
        else:
            await message.answer("Недействительный или уже использованный код")
    
    await message.answer("👋 Добро пожаловать!", reply_markup=get_main_menu_kb())
