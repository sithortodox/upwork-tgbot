import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.keyboard.inline import get_subscription_kb, get_back_kb
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
    
    text = "<b>💎 Подписка</b>\n\n"
    text += "Ваш план: 🆓 FREE\n\n"
    text += "<b>Free:</b> 5 генераций/день, базовые фильтры\n"
    text += "<b>Pro:</b> безлимит AI, расширенные фильтры, приоритет\n\n"
    text += "💰 <b>Цена: 499₽/мес</b>"
    
    await callback.message.edit_text(text, reply_markup=get_subscription_kb("free"))
    await callback.answer()

@router.callback_query(F.data == "sub_stars")
async def pay_stars(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SubscriptionFSM.payment)
    
    text = "<b>⭐ Оплата через Telegram Stars</b>\n\n"
    text += "30 дней Pro: ⭐ 50 Stars\n\n"
    text += "⚠️ Оплата в тестовом режиме"
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Оплатить (тест)", callback_data="stars_test")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="subscription")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "stars_test")
async def test_payment(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✅ Подписка активирована (тест)!\n\n"
        "💎 Pro активен на 30 дней",
        reply_markup=get_back_kb("main")
    )
    await callback.answer()

@router.callback_query(F.data == "sub_yookassa")
async def pay_yookassa(callback: CallbackQuery, state: FSMContext):
    text = "<b>💳 Оплата через ЮKassa</b>\n\n"
    text += "⚠️ Требуется настройка платежной системы"
    
    await callback.message.edit_text(text, reply_markup=get_back_kb("subscription"))
    await callback.answer()

@router.callback_query(F.data == "sub_referral")
async def show_referral(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SubscriptionFSM.referral)
    
    code = "ABC12345"
    bot_username = "test_upwork_test_bot"
    referral_link = f"https://t.me/{bot_username}?start={code}"
    
    text = f"<b>👥 Реферальная программа</b>\n\n"
    text += f"Ваша реферальная ссылка:\n<code>{referral_link}</code>\n\n"
    text += f"Приглашено: 0 человек\n"
    text += f"Заработано дней Pro: 0\n\n"
    text += "🎁 За каждого приглашенного — 7 дней Pro!"
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться", switch_inline_query=referral_link)],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="subscription")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()
