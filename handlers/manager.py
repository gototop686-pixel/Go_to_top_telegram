from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from config.config import config
from states.user_states import ManagerChat
from keyboards.reply import get_main_menu_kb

router = Router()

def get_manager_chat_kb() -> ReplyKeyboardMarkup:
    kb = [[KeyboardButton(text="❌ Завершить диалог")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@router.callback_query(F.data.startswith("accept_chat:"))
async def accept_chat_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = int(callback.data.split(":")[1])
    
    # Set manager state
    await state.set_state(ManagerChat.in_chat)
    await state.update_data(active_user_id=user_id)
    
    # Set user state globally so their messages are intercepted
    # We use the same storage key as the user
    from aiogram.fsm.storage.base import StorageKey
    user_state_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
    await callback.message.bot.get_context(user_state_key).set_state(ManagerChat.in_chat)
    
    await callback.message.edit_text(f"✅ Вы вошли в чат с пользователем {user_id}. Теперь ваши сообщения будут отправляться ему.")
    await callback.message.answer("Режим чата активен. Чтобы выйти, нажмите кнопку ниже.", reply_markup=get_manager_chat_kb())
    
    # Notify user
    try:
        await bot.send_message(user_id, "Менеджер подключился к чату! 🙋‍♂️ Вы можете писать свои сообщения здесь.")
    except Exception:
        pass
    
    await callback.answer()

@router.message(ManagerChat.in_chat)
async def forward_chat_message(message: Message, state: FSMContext, bot: Bot):
    # Check if this is the manager
    if message.from_user.id == config.manager_id:
        if message.text == "❌ Завершить диалог":
            await end_chat_handler(message, state, bot)
            return
            
        data = await state.get_data()
        user_id = data.get("active_user_id")
        if user_id:
            try:
                await bot.send_message(user_id, f"👨‍💼 Менеджер: {message.text}")
            except Exception as e:
                await message.answer(f"Ошибка при отправке: {e}")
    else:
        # This is a message FROM a USER to the manager
        from_user = message.from_user
        msg_to_manager = f"📩 Сообщение от {from_user.full_name} (@{from_user.username}):\n\n{message.text}"
        try:
            await bot.send_message(config.manager_id, msg_to_manager)
        except Exception:
            pass

async def end_chat_handler(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    user_id = data.get("active_user_id")
    
    # Manager's state
    await state.clear()
    await message.answer("Диалог завершен. Вы вернулись в обычный режим.", reply_markup=get_main_menu_kb(lambda x: x))
    
    # User's state
    if user_id:
        from aiogram.fsm.storage.base import StorageKey
        user_state_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
        await message.bot.get_context(user_state_key).clear()
        
        try:
            await bot.send_message(user_id, "Менеджер завершил диалог. Бот снова в автоматическом режиме! 🤖")
        except Exception:
            pass

# IMPORTANT: We also need to intercept USER messages if they are in ManagerChat.in_chat
# This would normally be in a separate logic or shared.
