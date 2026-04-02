from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from config.config import config
from states.user_states import ManagerChat
from keyboards.reply import get_main_menu_kb
from aiogram.fsm.storage.base import StorageKey
from middlewares.i18n import i18n_manager

router = Router()

def get_chat_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    # Use localized or bilingual text for the exit button
    text = "❌ Завершить диалог / Ավարտել"
    kb = [[KeyboardButton(text=text)]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@router.callback_query(F.data.startswith("accept_chat:"))
async def accept_chat_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = int(callback.data.split(":")[1])
    
    # Force manager state
    await state.set_state(ManagerChat.in_chat)
    await state.update_data(active_user_id=user_id)
    
    # Force user state
    user_state_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
    await bot.get_context(user_state_key).set_state(ManagerChat.in_chat)
    # Also save manager's ID to user's data so they know who is helping
    await bot.get_context(user_state_key).update_data(manager_id=config.manager_id)
    
    await callback.message.edit_text(f"✅ Чат с пользователем {user_id} активен.")
    
    # Send NEW keyboard to manager
    await callback.message.answer(
        "📝 Режим чата активен. Все сообщения идут клиенту.\n\n"
        "Чтобы выйти, нажмите на кнопку ниже 👇", 
        reply_markup=get_chat_kb("ru")
    )
    
    # Send NEW keyboard to user
    try:
        await bot.send_message(
            user_id, 
            "Лия (Менеджер) подключилась к чату! 👱‍♀️ Чем могу вам помочь?\n\n"
            "Вы можете завершить чат, нажав на кнопку ниже.",
            reply_markup=get_chat_kb("am")
        )
    except Exception:
        pass
    
    await callback.answer()

@router.message(ManagerChat.in_chat)
async def forward_chat_message(message: Message, state: FSMContext, bot: Bot):
    # Exit commands/text
    exit_texts = [
        "❌ Завершить диалог / Ավարտել",
        "Завершить диалог",
        "Ավարտել",
        i18n_manager.get("btn_back_to_menu", "ru"),
        i18n_manager.get("btn_back_to_menu", "am")
    ]
    
    if message.text in exit_texts:
        await end_chat_handler(message, state, bot)
        return

    data = await state.get_data()
    
    # MANAGER -> USER
    if message.from_user.id == config.manager_id:
        active_user_id = data.get("active_user_id")
        if active_user_id:
            try:
                await bot.send_message(active_user_id, f"👱‍♀️ Лия (Менеджер): {message.text}")
            except Exception as e:
                await message.answer(f"Ошибка: {e}")
    
    # USER -> MANAGER
    else:
        # Check if the manager ID is in config
        msg_to_manager = f"📩 Клиент {message.from_user.full_name}:\n\n{message.text}"
        try:
            await bot.send_message(config.manager_id, msg_to_manager)
        except Exception:
            pass

async def end_chat_handler(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    
    # If manager clicks exit
    if message.from_user.id == config.manager_id:
        user_id = data.get("active_user_id")
        await state.clear()
        await message.answer("Диалог завершен.", reply_markup=get_main_menu_kb(lambda x: "🔙 В меню"))
        
        if user_id:
            user_state_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
            await bot.get_context(user_state_key).clear()
            await bot.send_message(user_id, "Менеджер завершил диалог. Бот снова в режиме Лии! 🤖", reply_markup=get_main_menu_kb(lambda x: "Меню"))
            
    # If user clicks exit
    else:
        await state.clear()
        await message.answer("Диалог завершен. Чем еще я могу помочь? 🤖", reply_markup=get_main_menu_kb(lambda x: "Меню"))
        
        try:
            await bot.send_message(config.manager_id, f"⏹ Пользователь {message.from_user.full_name} завершил диалог.")
            # Clear manager state too if they were talking to THIS user
            manager_state_key = StorageKey(bot_id=bot.id, chat_id=config.manager_id, user_id=config.manager_id)
            m_ctx = bot.get_context(manager_state_key)
            m_data = await m_ctx.get_data()
            if m_data.get("active_user_id") == message.from_user.id:
                await m_ctx.clear()
                await bot.send_message(config.manager_id, "Ваш текущий чат закрыт.", reply_markup=get_main_menu_kb(lambda x: "Ок"))
        except Exception:
            pass
