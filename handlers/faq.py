"""
FAQ handler — Armenian static FAQ + Russian AI FAQ.
Armenian: shows a list of questions as buttons (grouped by category), answers statically.
Russian: redirects to AI support (Liya).
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from states.user_states import SupportMode
from keyboards.reply import get_main_menu_kb, get_faq_kb, get_ai_support_kb
from middlewares.i18n import i18n_manager
from handlers.faq_data import ARMENIAN_FAQ, ARMENIAN_FAQ_CATEGORIES

router = Router()

# Build a lookup dict: question_text -> answer
_FAQ_ANSWERS = {item["question"]: item["answer"] for item in ARMENIAN_FAQ}

# Build a set of category titles so we can handle taps on them
_CATEGORY_TITLES = {cat["title"] for cat in ARMENIAN_FAQ_CATEGORIES}


@router.message(F.text.in_([
    i18n_manager.get("btn_faq", "ru"),
    i18n_manager.get("btn_faq", "am")
]))
async def handle_faq_button(message: Message, i18n, language: str, state: FSMContext):
    """User pressed 'FAQ' button in main menu."""
    if language == "am":
        # Armenian: show static FAQ list as keyboard
        await message.answer(
            "\u0540\u0561\u0580\u0581\u0565\u0580 \u0587 \u057a\u0561\u057f\u0561\u057d\u056d\u0561\u0576\u0576\u0565\u0580 \u2753\n\n"
            "\u0538\u0576\u057f\u0580\u0565\u0584 \u0570\u0561\u0580\u0581\u0568\u055d",
            reply_markup=get_faq_kb(i18n),
            parse_mode=None
        )
    else:
        # Russian: go to AI support (Liya)
        await state.set_state(SupportMode.asking_question)
        await message.answer(
            i18n("ask_question_prompt"),
            reply_markup=get_ai_support_kb(i18n),
            parse_mode=None
        )


@router.message(F.text.in_(_CATEGORY_TITLES))
async def handle_category_header(message: Message, i18n, language: str):
    """User tapped a category header — just remind them to pick a question."""
    await message.answer(
        "\u0538\u0576\u057f\u0580\u0565\u0584 \u0570\u0561\u0580\u0581\u0568 \u057d\u057f\u0578\u0580\u0587\u0589 \U0001f447",
        reply_markup=get_faq_kb(i18n),
        parse_mode=None
    )


@router.message(F.text.in_(list(_FAQ_ANSWERS.keys())))
async def handle_faq_answer(message: Message, i18n, language: str):
    """User pressed one of the Armenian FAQ question buttons."""
    answer = _FAQ_ANSWERS.get(message.text)
    if answer:
        await message.answer(answer, reply_markup=get_faq_kb(i18n), parse_mode=None)
    else:
        await message.answer(
            "\u0540\u0561\u0580\u0581\u0568 \u0579\u0563\u057f\u0576\u057e\u0565\u0581\u0589",
            reply_markup=get_faq_kb(i18n),
            parse_mode=None
        )
