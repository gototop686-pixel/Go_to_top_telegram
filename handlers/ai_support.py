from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from states.user_states import SupportMode
from services.ai_service import ai_service
from database.crud import log_interaction
from keyboards.reply import get_main_menu_kb, get_ai_support_kb
from middlewares.i18n import i18n_manager

router = Router()

@router.message(F.text.in_([i18n_manager.get("btn_ask_question", "ru"), i18n_manager.get("btn_ask_question", "am")]))
async def start_questioning(message: Message, i18n, state: FSMContext):
    await state.set_state(SupportMode.asking_question)
    await message.answer(i18n("ask_question_prompt"), reply_markup=get_ai_support_kb(i18n))

@router.message(SupportMode.asking_question)
async def process_question(message: Message, i18n, language: str, state: FSMContext):
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
        await state.clear()
        from handlers.common import contact_manager
        await contact_manager(message, i18n)
        return

    # Trigger AI Mode
    answer = await ai_service.get_answer(message.text, language)
    
    # Log interaction
    await log_interaction(message.from_user.id, 'ai', 'questioning', message.text, answer)

    # Respond with AI answer and provide the specialized AI keyboard (Manager + Calc + Back)
    await message.answer(answer, reply_markup=get_ai_support_kb(i18n))
