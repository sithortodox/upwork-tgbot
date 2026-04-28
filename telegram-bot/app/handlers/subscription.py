import sys
sys.path.insert(0, '/app')

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
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
    
    await callback.message.edit_text(
        "<b>💎 Подписка</b>\n\n"
        "Free: 5 генераций/день\n"
        "Pro: безлимит AI\n\n"
        "💰 Цена: 499₽/мес\n\n"
        "Оплата временно недоступна.",
        reply_markup=get_back_kb("main")
    )
    await callback.answer()
