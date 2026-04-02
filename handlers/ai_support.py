from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from states.user_states import SupportMode
from services.ai_service import ai_service
from database.crud import log_interaction
from keyboards.reply import get_main_menu_kb, get_ai_support_kb
from middlewares.i18n import i18n_manager
from handlers.common import notify_manager_about_attempt

router = Router()

# Order keywords to trigger manager alerts
ORDER_KEYWORDS = ["артикул", "articul", "заказ", "order", "պատվեր", "хочу купить", "хочу заказать", "հաշվարկ", "расчет"]

@router.message(F.text.in_([i18n_manager.get("btn_ask_question", "ru"), i18n_manager.get("btn_ask_question", "am")]))
async def start_questioning(message: Message, i18n, state: FSMContext):
    await state.set_state(SupportMode.asking_question)
    await message.answer(i18n("ask_question_prompt"), reply_markup=get_ai_support_kb(i18n))

@router.message(SupportMode.asking_question)
async def process_question(message: Message, i18n, language: str, state: FSMContext, bot: Bot):
    # Match back button
    if message.text in [i18n_manager.get("btn_back_to_menu", "ru"), i18n_manager.get("btn_back_to_menu", "am")]:
        await state.clear()
        await message.answer(i18n("main_menu"), reply_markup=get_main_menu_kb(i18n))
        return
        
    # Match calculate on site button
    if message.text in [i18n_manager.get("btn_calc_on_site", "ru"), i18n_manager.get("btn_calc_on_site", "am")]:
        await message.answer(i18n("calc_on_site_msg"), reply_markup=get_ai_support_kb(i18n))
        return

    # Match contact manager button
    if message.text in [i18n_manager.get("btn_contact_manager", "ru"), i18n_manager.get("btn_contact_manager", "am")]:
        from handlers.common import contact_manager
        await contact_manager(message, i18n, bot)
        return

    # Trigger AI Answer
    answer = await ai_service.get_answer(message.text, language)
    
    # Log interaction
    await log_interaction(message.from_user.id, 'ai', 'questioning', message.text, answer)

    # Respond with AI answer and provide specialized AI keyboard
    await message.answer(answer, reply_markup=get_ai_support_kb(i18n))
    
    # SYSTEM UPGRADE: Automatic manager notifications on order keywords
    if any(k.lower() in message.text.lower() for k in ORDER_KEYWORDS):
        context = f"🔹 ВОПРОС: {message.text}\n🔸 ОТВЕТ ЛИИ: {answer[:300]}..."
        await notify_manager_about_attempt(bot, message.from_user, context)
