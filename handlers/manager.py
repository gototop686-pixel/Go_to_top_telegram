from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from config.config import config
from states.user_states import ManagerChat
from keyboards.reply import get_main_menu_kb
from aiogram.fsm.storage.base import StorageKey
from middlewares.i18n import i18n_manager

router = Router()

def get_chat_kb() -> ReplyKeyboardMarkup:
    # Always provide a clear bilingual exit button
    text = "❌ Завершить диалог / Ավարտել"
    kb = [[KeyboardButton(text=text)]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=False)

@router.callback_query(F.data.startswith("accept_chat:"))
async def accept_chat_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = int(callback.data.split(":")[1])
    
    # Force manager state
    await state.set_state(ManagerChat.in_chat)
    await state.update_data(active_user_id=user_id)
    
    # Force user state (FIX AttributeError)
    user_state_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
    user_ctx = FSMContext(storage=state.storage, key=user_state_key)
    
    await user_ctx.set_state(ManagerChat.in_chat)
    await user_ctx.update_data(manager_id=config.manager_id)
    
    await callback.message.edit_text(f"✅ Чат с пользователем {user_id} активен.")
    
    # Send NEW keyboard to manager to ensure the button is there
    await callback.message.answer(
        "📝 Режим чата Лия: Включен.\n\n"
        "Ваши сообщения отправляются клиенту. Для завершения нажмите кнопку ниже 👇", 
        reply_markup=get_chat_kb()
    )
    
    # Send NEW keyboard to user
    try:
        await bot.send_message(
            user_id, 
            "Лия (Менеджер) подключилась к чату! 👱‍♀️ Чем могу вам помочь?\n\n"
            "Вы можете писать мне напрямую. Чтобы вернуться к ИИ, нажмите кнопку ниже.",
            reply_markup=get_chat_kb()
        )
    except Exception:
        pass
    
    await callback.answer()

@router.message(ManagerChat.in_chat)
async def forward_chat_message(message: Message, state: FSMContext, bot: Bot):
    # Exit command check (bilingual + standard back buttons)
    exit_cmds = [
        "❌ Завершить диалог / Ավարտել",
        "Завершить диалог",
        "Ավարտել",
        "Назад в меню",
        "Վերադառնալ մենյու",
        "/start",
        "stop"
    ]
    
    if message.text in exit_cmds:
        await end_chat_handler(message, state, bot)
        return

    data = await state.get_data()
    
    # MANAGER -> USER
    if message.from_user.id == config.manager_id:
        user_id = data.get("active_user_id")
        if user_id:
            try:
                await bot.send_message(user_id, f"👱‍♀️ Лия (Менеджер): {message.text}")
            except Exception as e:
                await message.answer(f"Ошибка при оправке клиенту: {e}")
    
    # USER -> MANAGER
    else:
        # Message from user to manager
        msg_to_manager = f"📩 Сообщение от {message.from_user.full_name} (@{message.from_user.username}):\n\n{message.text}"
        try:
            await bot.send_message(config.manager_id, msg_to_manager)
        except Exception:
            pass

async def end_chat_handler(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    
    # If the manager ends the chat
    if message.from_user.id == config.manager_id:
        user_id = data.get("active_user_id")
        await state.clear()
        
        # Simple i18n lambda for manager (defaults to RU)
        await message.answer("Вы завершили диалог. Бот снова в режиме Лии.", reply_markup=get_main_menu_kb(lambda x: "Меню"))
        
        if user_id:
            user_state_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
            user_ctx = FSMContext(storage=state.storage, key=user_state_key)
            await user_ctx.clear()
            try:
                await bot.send_message(user_id, "Менеджер Лия завершила диалог. Чем еще я могу помочь? 🤖", reply_markup=get_main_menu_kb(lambda x: "Меню"))
            except Exception:
                pass
                
    # If the user ends the chat
    else:
        await state.clear()
        await message.answer("Диалог завершен. Лия готова отвечать на новые вопросы! 🤖", reply_markup=get_main_menu_kb(lambda x: "Меню"))
        
        try:
            await bot.send_message(config.manager_id, f"⏹ Пользователь {message.from_user.full_name} завершил диалог.")
            # Clear manager side too
            manager_state_key = StorageKey(bot_id=bot.id, chat_id=config.manager_id, user_id=config.manager_id)
            m_ctx = FSMContext(storage=state.storage, key=manager_state_key)
            m_data = await m_ctx.get_data()
            if m_data.get("active_user_id") == message.from_user.id:
                await m_ctx.clear()
                await bot.send_message(config.manager_id, "Ваша сессия также закрыта.", reply_markup=get_main_menu_kb(lambda x: "Ок"))
        except Exception:
            pass
