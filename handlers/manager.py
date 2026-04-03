import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from config.config import config
from states.user_states import ManagerChat
from keyboards.reply import get_main_menu_kb
from aiogram.fsm.storage.base import StorageKey
from middlewares.i18n import i18n_manager
from database.crud import get_user

router = Router()


# ============================================================
# MULTI-CHAT SYSTEM
# ============================================================
# manager can talk to multiple clients simultaneously.
# "active" chat = the one messages are routed to right now.
# Other chats stay "open" (paused) — client messages still arrive,
# manager can switch back at any time.
#
# Data structures (in-memory, per manager):
#   open_chats[manager_id] = {user_id: {"name": ..., "username": ...}, ...}
#   active_chat[manager_id] = user_id | None
# ============================================================

open_chats: dict[int, dict[int, dict]] = {}   # manager -> {user_id -> info}
active_chat: dict[int, int | None] = {}         # manager -> current user_id


def _get_open(mgr: int) -> dict[int, dict]:
    return open_chats.setdefault(mgr, {})


def _get_active(mgr: int) -> int | None:
    return active_chat.get(mgr)


def _set_active(mgr: int, uid: int | None):
    active_chat[mgr] = uid


# ============================================================
# KEYBOARDS
# ============================================================

def get_manager_chat_kb(manager_id: int) -> ReplyKeyboardMarkup:
    """Dynamic keyboard showing open chats + controls."""
    chats = _get_open(manager_id)
    active = _get_active(manager_id)
    rows = []

    if len(chats) > 1:
        # Switch buttons for each non-active chat
        for uid, info in chats.items():
            if uid == active:
                continue
            name = info.get("name", str(uid))
            rows.append([KeyboardButton(text=f"🔀 {name} [{uid}]")])

    rows.append([KeyboardButton(text="❌ Завершить диалог / Ավարտել")])
    rows.append([KeyboardButton(text="📋 Список чатов")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=False)


def get_switch_inline_kb(manager_id: int) -> InlineKeyboardMarkup | None:
    """Inline keyboard to switch to a specific chat (used in notifications)."""
    chats = _get_open(manager_id)
    if not chats:
        return None
    buttons = []
    for uid, info in chats.items():
        name = info.get("name", str(uid))
        buttons.append([InlineKeyboardButton(
            text=f"💬 {name}",
            callback_data=f"switch_chat:{uid}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================
# HELPERS
# ============================================================

def get_i18n_for_user(language: str = "ru"):
    def i18n(key, **kwargs):
        return i18n_manager.get(key, language, **kwargs)
    return i18n


async def get_user_fsm(bot: Bot, storage, user_id: int) -> FSMContext:
    key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)


async def _activate_chat(manager_id: int, user_id: int, bot: Bot, state: FSMContext, storage):
    """Make a chat active: set FSM states, update tracking, send keyboard."""
    chats = _get_open(manager_id)
    info = chats.get(user_id, {})
    name = info.get("name", str(user_id))

    _set_active(manager_id, user_id)

    # Set manager FSM
    await state.set_state(ManagerChat.in_chat)
    await state.update_data(active_user_id=user_id)

    # Set user FSM
    user_ctx = await get_user_fsm(bot, storage, user_id)
    await user_ctx.set_state(ManagerChat.in_chat)
    await user_ctx.update_data(connected_manager_id=manager_id)

    return name


async def _close_chat(manager_id: int, user_id: int, bot: Bot, state: FSMContext, storage):
    """Close one chat, notify client, clean up."""
    chats = _get_open(manager_id)
    info = chats.pop(user_id, {})
    name = info.get("name", str(user_id))

    # If this was the active chat, clear active
    if _get_active(manager_id) == user_id:
        _set_active(manager_id, None)

    # Clear user FSM
    user_ctx = await get_user_fsm(bot, storage, user_id)
    await user_ctx.clear()

    # Notify user
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
        logging.error(f"Failed to notify user {user_id} about chat end: {e}")

    return name


# ============================================================
# ACCEPT CHAT (manager clicks inline button under lead notification)
# ============================================================

@router.callback_query(F.data.startswith("accept_chat:"))
async def accept_chat_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = int(callback.data.split(":")[1])
    manager_id = callback.from_user.id

    chats = _get_open(manager_id)

    # Already chatting with this user?
    if user_id in chats:
        # Just switch to them
        name = await _activate_chat(manager_id, user_id, bot, state, state.storage)
        await callback.answer(f"Переключено на {name}")
        await bot.send_message(
            manager_id,
            f"🔀 Переключено на чат с {name} (ID: {user_id})",
            reply_markup=get_manager_chat_kb(manager_id),
            parse_mode=None
        )
        return

    # Add new chat (don't edit the original message — keep lead data visible!)
    user_obj = callback.from_user  # This is manager, we need client info
    # Get client info from callback message text
    client_name = f"Клиент {user_id}"
    client_username = ""

    # Try to parse name from the notification message
    if callback.message and callback.message.text:
        import re
        name_match = re.search(r'Клиент:\s*(.+)', callback.message.text)
        if name_match:
            client_name = name_match.group(1).strip()
        username_match = re.search(r'Telegram:\s*@(\S+)', callback.message.text)
        if username_match:
            client_username = username_match.group(1).strip()

    chats[user_id] = {"name": client_name, "username": client_username}

    # Activate this chat
    name = await _activate_chat(manager_id, user_id, bot, state, state.storage)

    # DON'T edit_text — that destroys the lead data!
    # Instead, reply below the original message
    try:
        await callback.message.reply(
            f"✅ Чат с {client_name} (ID: {user_id}) активен.",
            parse_mode=None
        )
    except Exception:
        await bot.send_message(
            manager_id,
            f"✅ Чат с {client_name} (ID: {user_id}) активен.",
            parse_mode=None
        )

    # Send keyboard
    total = len(chats)
    await bot.send_message(
        manager_id,
        f"📝 Режим чата с {client_name}.\n"
        f"Открыто чатов: {total}\n"
        f"Ваши сообщения → клиенту.\n"
        f"Для переключения используйте кнопки 👇",
        reply_markup=get_manager_chat_kb(manager_id),
        parse_mode=None
    )

    # Notify client
    try:
        await bot.send_message(
            user_id,
            "Менеджер подключился к чату! 👋 Сейчас с вами общается наш специалист.",
            parse_mode=None
        )
    except Exception as e:
        logging.error(f"Failed to notify user {user_id}: {e}")

    await callback.answer()


# ============================================================
# SWITCH CHAT (inline button)
# ============================================================

@router.callback_query(F.data.startswith("switch_chat:"))
async def switch_chat_inline(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = int(callback.data.split(":")[1])
    manager_id = callback.from_user.id
    chats = _get_open(manager_id)

    if user_id not in chats:
        await callback.answer("Этот чат уже закрыт.", show_alert=True)
        return

    name = await _activate_chat(manager_id, user_id, bot, state, state.storage)
    await callback.answer(f"Переключено на {name}")
    await bot.send_message(
        manager_id,
        f"🔀 Активный чат: {name} (ID: {user_id})",
        reply_markup=get_manager_chat_kb(manager_id),
        parse_mode=None
    )


# ============================================================
# MANAGER IN CHAT — message routing
# ============================================================

@router.message(ManagerChat.in_chat)
async def forward_chat_message(message: Message, state: FSMContext, bot: Bot):
    sender_id = message.from_user.id

    if not message.text:
        return

    text = message.text.strip()

    # ---- EXIT ----
    exit_cmds = [
        "❌ Завершить диалог / Ավарտել",
        "Завершить диалог",
        "Ավարտել",
        "/end", "/stop",
    ]
    if text in exit_cmds:
        await end_active_chat(message, state, bot)
        return

    if text == "/start":
        await end_all_chats(message, state, bot)
        return

    # ---- CHAT LIST ----
    if text == "📋 Список чатов":
        await show_chat_list(message, state, bot)
        return

    # ---- SWITCH via keyboard button "🔀 Name [ID]" ----
    if text.startswith("🔀 "):
        import re
        match = re.search(r'\[(\d+)\]', text)
        if match:
            target_uid = int(match.group(1))
            chats = _get_open(sender_id)
            if target_uid in chats:
                name = await _activate_chat(sender_id, target_uid, bot, state, state.storage)
                await message.answer(
                    f"🔀 Активный чат: {name} (ID: {target_uid})",
                    reply_markup=get_manager_chat_kb(sender_id),
                    parse_mode=None
                )
                return
            else:
                await message.answer("Этот чат уже закрыт.", parse_mode=None)
                return

    # ---- ROUTE MESSAGE ----
    if sender_id == config.manager_id:
        # MANAGER -> active client
        active_uid = _get_active(sender_id)
        if active_uid:
            try:
                await bot.send_message(active_uid, text, parse_mode=None)
            except Exception as e:
                await message.answer(f"Ошибка отправки клиенту: {e}", parse_mode=None)
        else:
            await message.answer(
                "Нет активного чата. Выберите клиента из списка 👇",
                reply_markup=get_switch_inline_kb(sender_id) or None,
                parse_mode=None
            )
    else:
        # CLIENT -> manager
        data = await state.get_data()
        manager_id = data.get("connected_manager_id", config.manager_id)
        client_name = message.from_user.full_name or "Клиент"
        username = message.from_user.username or "N/A"

        active_for_manager = _get_active(manager_id)

        # Mark if this isn't the currently active chat
        prefix = ""
        if active_for_manager != sender_id:
            prefix = "⚠️ [другой чат] "

        try:
            await bot.send_message(
                manager_id,
                f"📩 {prefix}[{client_name} @{username}]:\n{text}",
                parse_mode=None
            )
        except Exception as e:
            logging.error(f"Failed to forward to manager: {e}")


# ============================================================
# CHAT MANAGEMENT
# ============================================================

async def show_chat_list(message: Message, state: FSMContext, bot: Bot):
    manager_id = message.from_user.id
    chats = _get_open(manager_id)
    active = _get_active(manager_id)

    if not chats:
        await message.answer("Нет открытых чатов.", parse_mode=None)
        return

    lines = ["📋 Открытые чаты:\n"]
    for uid, info in chats.items():
        name = info.get("name", str(uid))
        marker = " ← активный" if uid == active else ""
        lines.append(f"{'🟢' if uid == active else '⚪'} {name} (ID: {uid}){marker}")

    lines.append(f"\nВсего: {len(chats)}")

    await message.answer(
        "\n".join(lines),
        reply_markup=get_manager_chat_kb(manager_id),
        parse_mode=None
    )


async def end_active_chat(message: Message, state: FSMContext, bot: Bot):
    """Close only the currently active chat, switch to next if available."""
    manager_id = message.from_user.id
    active_uid = _get_active(manager_id)

    if not active_uid:
        await message.answer("Нет активного чата для завершения.", parse_mode=None)
        return

    name = await _close_chat(manager_id, active_uid, bot, state, state.storage)

    chats = _get_open(manager_id)

    if chats:
        # Auto-switch to next available chat
        next_uid = next(iter(chats))
        next_name = await _activate_chat(manager_id, next_uid, bot, state, state.storage)
        await message.answer(
            f"✅ Чат с {name} завершён.\n"
            f"🔀 Автопереключение на {next_name} (ID: {next_uid}).\n"
            f"Открыто чатов: {len(chats)}",
            reply_markup=get_manager_chat_kb(manager_id),
            parse_mode=None
        )
    else:
        # No more chats — exit chat mode
        await state.clear()
        manager_i18n = get_i18n_for_user("ru")
        await message.answer(
            f"✅ Чат с {name} завершён. Все диалоги закрыты.\nБот снова отвечает клиентам.",
            reply_markup=get_main_menu_kb(manager_i18n),
            parse_mode=None
        )


async def end_all_chats(message: Message, state: FSMContext, bot: Bot):
    """Close ALL open chats (e.g. on /start)."""
    manager_id = message.from_user.id
    chats = _get_open(manager_id)

    for uid in list(chats.keys()):
        await _close_chat(manager_id, uid, bot, state, state.storage)

    open_chats.pop(manager_id, None)
    active_chat.pop(manager_id, None)
    await state.clear()

    manager_i18n = get_i18n_for_user("ru")
    await message.answer(
        "Все диалоги завершены. Бот снова отвечает клиентам.",
        reply_markup=get_main_menu_kb(manager_i18n),
        parse_mode=None
    )
