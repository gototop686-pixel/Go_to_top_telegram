from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from config.config import config
from states.user_states import ManagerChat
from keyboards.reply import get_main_menu_kb
from aiogram.fsm.storage.base import StorageKey

router = Router()

def get_manager_chat_kb() -> ReplyKeyboardMarkup:
    kb = [[KeyboardButton(text="❌ Завершить диалог")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=False)

@router.callback_query(F.data.startswith("accept_chat:"))
async def accept_chat_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = int(callback.data.split(":")[1])
    
    # Set manager state
    await state.set_state(ManagerChat.in_chat)
    await state.update_data(active_user_id=user_id)
    
    # Set user state globally
    user_state_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
    await bot.get_context(user_state_key).set_state(ManagerChat.in_chat)
    
    await callback.message.edit_text(f"✅ Чат с пользователем {user_id} активен.")
    await callback.message.answer(
        "📝 Теперь ваши сообщения отправляются клиенту.\n\n"
        "Чтобы выйти, используйте кнопку «❌ Завершить диалог» ниже.", 
        reply_markup=get_manager_chat_kb()
    )
    
    # Notify user
    try:
        await bot.send_message(user_id, "Лия (Менеджер) подключилась к чату! 👱‍♀️ Чем могу вам помочь?")
    except Exception:
        pass
    
    await callback.answer()

@router.message(ManagerChat.in_chat)
async def forward_chat_message(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    active_user_id = data.get("active_user_id")
    
    # MANAGER -> USER
    if message.from_user.id == config.manager_id:
        if message.text == "❌ Завершить диалог":
            await end_chat_handler(message, state, bot)
            return
            
        if active_user_id:
            try:
                # User's prefix
                prefix = "👱‍♀️ Лия (Менеджер):"
                await bot.send_message(active_user_id, f"{prefix} {message.text}")
            except Exception as e:
                await message.answer(f"Ошибка при пересылке клиенту: {e}")
    
    # USER -> MANAGER
    else:
        # If this is the user who is being helped
        from_user = message.from_user
        msg_to_manager = f"📩 Клиент {from_user.full_name} (@{from_user.username}):\n\n{message.text}"
        try:
            await bot.send_message(config.manager_id, msg_to_manager)
        except Exception:
            pass

async def end_chat_handler(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    user_id = data.get("active_user_id")
    
    # Manager side
    await state.clear()
    # Provide a simple keyboard to the manager to return to normal bot mode
    # Assuming manager uses RU
    await message.answer("Диалог завершен. Вы вернулись в режим управления ботом.", reply_markup=get_main_menu_kb(lambda x: x))
    
    # User side
    if user_id:
        user_state_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
        await bot.get_context(user_state_key).clear()
        
        try:
            await bot.send_message(user_id, "Менеджер Лия завершила диалог. Я снова в автоматическом режиме! 🤖")
        except Exception:
            pass
