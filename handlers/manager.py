import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from config.config import config
from states.user_states import ManagerChat
from keyboards.reply import get_main_menu_kb
from aiogram.fsm.storage.base import StorageKey
from middlewares.i18n import i18n_manager
from database.crud import get_user

router = Router()

# In-memory tracking of active manager<->user connections
active_connections = {}  # manager_id -> user_id


def get_chat_kb() -> ReplyKeyboardMarkup:
    kb = [[KeyboardButton(text="❌ Завершить диалог / Ավարտել")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=False)


def get_i18n_for_user(language: str = "ru"):
    """Create i18n function for a given language."""
    def i18n(key, **kwargs):
        return i18n_manager.get(key, language, **kwargs)
    return i18n


async def get_user_fsm(bot: Bot, storage, user_id: int) -> FSMContext:
    """Get FSM context for a specific user."""
    key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)


@router.callback_query(F.data.startswith("accept_chat:"))
async def accept_chat_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = int(callback.data.split(":")[1])
    manager_id = callback.from_user.id
    
    # Check if manager already connected to someone
    if manager_id in active_connections:
        old_user = active_connections[manager_id]
        if old_user != user_id:
            await callback.answer(
                f"Вы уже подключены к пользователю {old_user}. Сначала завершите текущий диалог.",
                show_alert=True
            )
            return
    
    # Set manager state
    await state.set_state(ManagerChat.in_chat)
    await state.update_data(active_user_id=user_id)
    
    # Set user state
    user_ctx = await get_user_fsm(bot, state.storage, user_id)
    await user_ctx.set_state(ManagerChat.in_chat)
    await user_ctx.update_data(connected_manager_id=manager_id)
    
    # Track connection
    active_connections[manager_id] = user_id
    
    await callback.message.edit_text(f"✅ Чат с пользователем {user_id} активен.")
    
    # Send keyboard to manager
    await bot.send_message(
        manager_id,
        "📝 Режим чата: включён.\n"
        "Ваши сообщения отправляются клиенту.\n"
        "Для завершения нажмите кнопку ниже 👇",
        reply_markup=get_chat_kb()
    )
    
    # Notify user
    try:
        await bot.send_message(
            user_id,
            "Менеджер подключился к чату! 👋 Сейчас с вами общается наш специалист.",
            reply_markup=get_chat_kb(),
            parse_mode=None
        )
    except Exception as e:
        logging.error(f"Failed to notify user {user_id}: {e}")
    
    await callback.answer()


@router.message(ManagerChat.in_chat)
async def forward_chat_message(message: Message, state: FSMContext, bot: Bot):
    # Check exit commands
    exit_cmds = [
        "❌ Завершить диалог / Ավարտել",
        "Завершить диалог",
        "Ավարտել",
        "/end",
        "/stop",
    ]
    
    if message.text and message.text.strip() in exit_cmds:
        await end_chat(message, state, bot)
        return
    
    # Also handle /start as exit
    if message.text and message.text.strip() == "/start":
        await end_chat(message, state, bot)
        return

    data = await state.get_data()
    
    # MANAGER -> USER
    if message.from_user.id == config.manager_id:
        user_id = data.get("active_user_id")
        if user_id:
            try:
                await bot.send_message(user_id, message.text, parse_mode=None)
            except Exception as e:
                await message.answer(f"Ошибка отправки клиенту: {e}", parse_mode=None)
        else:
            await message.answer("Нет активного клиента. Нажмите 'Завершить диалог'.", parse_mode=None)
    
    # USER -> MANAGER
    else:
        manager_id = data.get("connected_manager_id", config.manager_id)
        client_name = message.from_user.full_name or "Клиент"
        username = message.from_user.username or "N/A"
        
        try:
            await bot.send_message(
                manager_id,
                f"📩 [{client_name} @{username}]:\n{message.text}",
                parse_mode=None
            )
        except Exception as e:
            logging.error(f"Failed to forward to manager: {e}")


async def end_chat(message: Message, state: FSMContext, bot: Bot):
    """End the manager<->user chat and restore AI mode."""
    data = await state.get_data()
    sender_id = message.from_user.id
    
    if sender_id == config.manager_id:
        # Manager ends chat
        user_id = data.get("active_user_id")
        await state.clear()
        
        # Remove from active connections
        active_connections.pop(sender_id, None)
        
        # Get manager's i18n
        manager_i18n = get_i18n_for_user("ru")
        await message.answer(
            "Диалог завершён. Бот снова отвечает клиенту.",
            reply_markup=get_main_menu_kb(manager_i18n),
            parse_mode=None
        )
        
        if user_id:
            # Clear user state
            user_ctx = await get_user_fsm(bot, state.storage, user_id)
            await user_ctx.clear()
            
            # Get user language for proper keyboard
            user_data = await get_user(user_id)
            user_lang = user_data.get("language", "ru") if user_data else "ru"
            user_i18n = get_i18n_for_user(user_lang)
            
            try:
                await bot.send_message(
                    user_id,
                    "Менеджер завершил диалог. Если будут вопросы — я всегда на связи! 🎯",
                    reply_markup=get_main_menu_kb(user_i18n),
                    parse_mode=None
                )
            except Exception as e:
                logging.error(f"Failed to notify user about chat end: {e}")
    
    else:
        # User ends chat
        await state.clear()
        
        # Get user language
        user_data = await get_user(sender_id)
        user_lang = user_data.get("language", "ru") if user_data else "ru"
        user_i18n = get_i18n_for_user(user_lang)
        
        await message.answer(
            "Диалог завершён. Чем ещё могу помочь? 🎯",
            reply_markup=get_main_menu_kb(user_i18n),
            parse_mode=None
        )
        
        # Notify manager and clear their state
        try:
            # Find and clear manager connection
            manager_to_clear = None
            for mgr_id, usr_id in active_connections.items():
                if usr_id == sender_id:
                    manager_to_clear = mgr_id
                    break
            
            if manager_to_clear:
                active_connections.pop(manager_to_clear, None)
                manager_ctx = await get_user_fsm(bot, state.storage, manager_to_clear)
                manager_data = await manager_ctx.get_data()
                if manager_data.get("active_user_id") == sender_id:
                    await manager_ctx.clear()
                
                manager_i18n = get_i18n_for_user("ru")
                await bot.send_message(
                    manager_to_clear,
                    f"Клиент {message.from_user.full_name} завершил диалог.",
                    reply_markup=get_main_menu_kb(manager_i18n),
                    parse_mode=None
                )
        except Exception as e:
            logging.error(f"Failed to notify manager about user disconnect: {e}")
