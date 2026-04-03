import logging
import re
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from config.config import config
from states.user_states import ManagerChat
from keyboards.reply import get_main_menu_kb
from aiogram.fsm.storage.base import StorageKey
from middlewares.i18n import i18n_manager
from database.crud import (
    get_user, map_message, get_client_msg_id, 
    start_chat_session, end_chat_session,
    get_active_sessions_count, get_closed_sessions_today,
    get_pending_requests, accept_chat_request,
    clear_finished_sessions_today, clear_all_pending_requests
)

router = Router()


# ============================================================
# MULTI-CHAT SYSTEM
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

def get_client_chat_kb() -> ReplyKeyboardMarkup:
    """Minimal keyboard for CLIENT while in chat with manager.
    Only 'end chat' button — no menu, no other actions."""
    kb = [[KeyboardButton(text="❌ Завершить чат")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=False)


def get_manager_chat_kb(manager_id: int) -> ReplyKeyboardMarkup:
    """Dynamic keyboard for MANAGER showing open chats + controls."""
    chats = _get_open(manager_id)
    active = _get_active(manager_id)
    rows = []

    if len(chats) > 1:
        for uid, info in chats.items():
            if uid == active:
                continue
            name = info.get("name", str(uid))
            rows.append([KeyboardButton(text=f"🔀 {name} [{uid}]")])

    rows.append([KeyboardButton(text="❌ Завершить диалог / Ավարտել")])
    rows.append([KeyboardButton(text="📊 Панель управления")])
    rows.append([KeyboardButton(text="📋 Список чатов")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=False)


def get_dashboard_inline_kb() -> InlineKeyboardMarkup:
    """Dashboard control panel."""
    buttons = [
        [InlineKeyboardButton(text="🟢 Активные чаты", callback_data="dash:active")],
        [InlineKeyboardButton(text="🔔 Запросы на чат", callback_data="dash:requests")],
        [InlineKeyboardButton(text="✅ Завершённые сегодня", callback_data="dash:finished")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="dash:refresh")],
        [InlineKeyboardButton(text="🚨 Сбросить все чаты", callback_data="dash:reset_all")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_switch_inline_kb(manager_id: int) -> InlineKeyboardMarkup | None:
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
# CLIENT MENU BUTTONS (to intercept during chat)
# ============================================================

# All possible menu button texts that client might press (both languages)
CLIENT_MENU_BUTTONS = set()

def _load_menu_buttons():
    """Load all menu button texts from locales so we can block them during chat."""
    btn_keys = [
        "btn_new_client", "btn_existing_client", "btn_ask_question",
        "btn_contact_manager", "btn_calc_on_site", "btn_back_to_menu",
        "btn_check_status", "btn_faq", "btn_price_list", "btn_how_to_order",
        "btn_about_us", "btn_change_language",
        "btn_price_main", "btn_price_reviews", "btn_price_photo_video",
        "btn_price_fulfillment", "btn_price_delivery",
    ]
    for lang in ("ru", "am"):
        for key in btn_keys:
            text = i18n_manager.get(key, lang)
            if text:
                CLIENT_MENU_BUTTONS.add(text)

_load_menu_buttons()


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
    """Make a chat active: set FSM states, update tracking."""
    chats = _get_open(manager_id)
    info = chats.get(user_id, {})
    name = info.get("name", str(user_id))

    _set_active(manager_id, user_id)

    # Set manager FSM
    await state.set_state(ManagerChat.in_chat)
    await state.update_data(active_user_id=user_id)

    # Set user FSM — give them the minimal chat keyboard
    user_ctx = await get_user_fsm(bot, storage, user_id)
    await user_ctx.set_state(ManagerChat.in_chat)
    await user_ctx.update_data(connected_manager_id=manager_id)

    # Database: Start session
    await start_chat_session(user_id, manager_id)

    return name


async def _close_chat_for_client(manager_id: int, user_id: int, bot: Bot, storage,
                                  notify_client: bool = True, ended_by: str = "manager"):
    """Close one chat: clean user FSM, notify client, remove from tracking."""
    chats = _get_open(manager_id)
    info = chats.pop(user_id, {})
    name = info.get("name", str(user_id))

    if _get_active(manager_id) == user_id:
        _set_active(manager_id, None)

    # Clear user FSM
    user_ctx = await get_user_fsm(bot, storage, user_id)
    await user_ctx.clear()

    # Database: End session
    await end_chat_session(user_id)

    # Restore normal menu for client
    if notify_client:
        user_data = await get_user(user_id)
        user_lang = user_data.get("language", "ru") if user_data else "ru"
        user_i18n = get_i18n_for_user(user_lang)

        if ended_by == "manager":
            text = "Менеджер завершил диалог. Если будут вопросы — я всегда на связи! 🎯"
        else:
            text = "Вы вышли из чата с менеджером. Если будут вопросы — я всегда на связи! 🎯"

        try:
            await bot.send_message(
                user_id,
                text,
                reply_markup=get_main_menu_kb(user_i18n),
                parse_mode=None
            )
        except Exception as e:
            logging.error(f"Failed to notify user {user_id} about chat end: {e}")

    return name


# ============================================================
# SLASH COMMANDS — work ANY time, no active chat needed
# ============================================================

from aiogram.filters import Command


@router.message(Command("dashboard", "panel", "dash"))
async def cmd_dashboard(message: Message):
    """Manager can call /dashboard at any time."""
    if message.from_user.id != config.manager_id:
        return
    await show_dashboard(message)


@router.message(Command("chats", "list"))
async def cmd_chats(message: Message, state: FSMContext, bot: Bot):
    """Manager can call /chats at any time to see open chats."""
    if message.from_user.id != config.manager_id:
        return
    await show_chat_list(message, state, bot)


# ============================================================
# TEXT TRIGGERS — work outside of chat mode too
# ============================================================

@router.message(F.text == "📊 Панель управления")
async def text_dashboard(message: Message):
    if message.from_user.id != config.manager_id:
        return
    await show_dashboard(message)


@router.message(F.text == "📋 Список чатов")
async def text_chat_list(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != config.manager_id:
        return
    await show_chat_list(message, state, bot)


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
        name = await _activate_chat(manager_id, user_id, bot, state, state.storage)
        await callback.answer(f"Переключено на {name}")
        await bot.send_message(
            manager_id,
            f"🔀 Переключено на чат с {name} (@{chats[user_id].get('username', 'N/A')}) (ID: {user_id})",
            reply_markup=get_manager_chat_kb(manager_id),
            parse_mode=None
        )
        return

    # Get client info — try Telegram API first, then parse from message
    client_name = ""
    client_username = ""

    # Try to get real name from Telegram
    try:
        chat_info = await bot.get_chat(user_id)
        client_name = chat_info.full_name or ""
        client_username = chat_info.username or ""
    except Exception:
        pass

    # Fallback: parse from notification message
    if not client_name and callback.message and callback.message.text:
        for pattern in [r'Клиент:\s*(.+)', r'Имя:\s*(.+)', r'Անուն:\s*(.+)', r'👤\s*(.+)']:
            name_match = re.search(pattern, callback.message.text)
            if name_match:
                client_name = name_match.group(1).strip()
                break
        
        if not client_username:
            username_match = re.search(r'@(\w+)', callback.message.text)
            if username_match:
                client_username = username_match.group(1).strip()

    # Last resort
    if not client_name:
        client_name = f"Клиент {user_id}"

    chats[user_id] = {"name": client_name, "username": client_username}

    # Mark pending requests as accepted
    await accept_chat_request(user_id)

    # Activate this chat
    name = await _activate_chat(manager_id, user_id, bot, state, state.storage)

    # DON'T edit_text — keep lead data visible!
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

    # Manager keyboard
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

    # Client gets MINIMAL keyboard — only "end chat"
    try:
        await bot.send_message(
            user_id,
            "Менеджер подключился к чату! 👋\nСейчас с вами общается наш специалист.\n\nДля завершения нажмите кнопку ниже.",
            reply_markup=get_client_chat_kb(),
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
        f"🔀 Активный чат: {name} (@{chats[user_id].get('username', 'N/A')}) (ID: {user_id})",
        reply_markup=get_manager_chat_kb(manager_id),
        parse_mode=None
    )


# ============================================================
# IN-CHAT MESSAGE ROUTING
# ============================================================

@router.message(ManagerChat.in_chat)
async def forward_chat_message(message: Message, state: FSMContext, bot: Bot):
    sender_id = message.from_user.id
    text = message.text.strip() if message.text else message.caption.strip() if message.caption else ""

    # ---- EXIT COMMANDS (both manager and client) ----
    exit_cmds = [
        "❌ Завершить диалог / Ավարտել",  # manager button
        "❌ Завершить чат",                 # client button
        "Завершить диалог",
        "Завершить чат",
        "Ավարտել",
        "/end", "/stop",
    ]
    if text in exit_cmds:
        if sender_id == config.manager_id:
            await end_active_chat_by_manager(message, state, bot)
        else:
            await end_chat_by_client(message, state, bot)
        return

    # /start — manager: close all; client: exit chat
    if text == "/start":
        if sender_id == config.manager_id:
            await end_all_chats(message, state, bot)
        else:
            await end_chat_by_client(message, state, bot)
        return

    # ---- MANAGER-ONLY CONTROLS ----
    if sender_id == config.manager_id:
        if text == "📋 Список чатов":
            await show_chat_list(message, state, bot)
            return

        if text == "📊 Панель управления":
            await show_dashboard(message)
            return

        if text.startswith("🔀 "):
            match = re.search(r'\[(\d+)\]', text)
            if match:
                target_uid = int(match.group(1))
                chats = _get_open(sender_id)
                if target_uid in chats:
                    name = await _activate_chat(sender_id, target_uid, bot, state, state.storage)
                    await message.answer(
                        f"🔀 Активный чат: {name} (@{chats[target_uid].get('username', 'N/A')}) (ID: {target_uid})",
                        reply_markup=get_manager_chat_kb(sender_id),
                        parse_mode=None
                    )
                else:
                    await message.answer("Этот чат уже закрыт.", parse_mode=None)
                return

        # MANAGER -> active client
        active_uid = _get_active(sender_id)
        if active_uid:
            chats = _get_open(sender_id)
            info = chats.get(active_uid, {})
            name = info.get("name", "Клиент")
            username = info.get("username", "N/A")

            try:
                # Forward everything (media + text) to client
                cl_msg = await bot.copy_message(
                    chat_id=active_uid,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                # Map messages for sync (edit/delete)
                await map_message(message.chat.id, message.message_id, active_uid, cl_msg.message_id)

                # Small confirmation — show client name clearly
                confirm_name = name if name != f"Клиент {active_uid}" else name
                confirm_un = f" (@{username})" if username and username != "N/A" else ""
                await message.reply(
                    f"✅ → {confirm_name}{confirm_un}",
                    parse_mode=None
                )
            except Exception as e:
                await message.answer(f"Ошибка отправки клиенту: {e}", parse_mode=None)
        else:
            await message.answer(
                "Нет активного чата. Выберите клиента из списка 👇",
                reply_markup=get_switch_inline_kb(sender_id) or None,
                parse_mode=None
            )
        return

    # ---- CLIENT SENDING MESSAGE ----

    # Block menu button presses — don't forward to manager
    if text in CLIENT_MENU_BUTTONS:
        await message.answer(
            "Сейчас вы в чате с менеджером.\n"
            "Чтобы вернуться в меню, сначала завершите чат 👇",
            reply_markup=get_client_chat_kb(),
            parse_mode=None
        )
        return

    # Forward client message to manager
    data = await state.get_data()
    manager_id = data.get("connected_manager_id", config.manager_id)
    client_name = message.from_user.full_name or "Клиент"
    username = message.from_user.username or "N/A"

    active_for_manager = _get_active(manager_id)
    prefix = ""
    if active_for_manager != sender_id:
        prefix = "⚠️ [другой чат] "

    try:
        # First send who it's from if it's media or has no text
        info_text = f"📩 {prefix}[{client_name} @{username}]"
        
        # If it's just text, send it normally
        if message.text:
            await bot.send_message(
                manager_id,
                f"{info_text}:\n{message.text}",
                parse_mode=None
            )
        else:
            # If it's media, send info text first, then copy the media
            await bot.send_message(manager_id, f"{info_text}:", parse_mode=None)
            await bot.copy_message(
                chat_id=manager_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            
    except Exception as e:
        logging.error(f"Failed to forward to manager: {e}")


@router.edited_message(ManagerChat.in_chat)
async def sync_manager_edit(message: Message, bot: Bot):
    """Sync manager edits to client."""
    if message.from_user.id != config.manager_id:
        return
    
    cl_msg_id = await get_client_msg_id(message.chat.id, message.message_id)
    if not cl_msg_id:
        return

    active_uid = _get_active(message.from_user.id)
    if not active_uid:
        return

    try:
        if message.text:
            await bot.edit_message_text(
                text=message.text,
                chat_id=active_uid,
                message_id=cl_msg_id
            )
        elif message.caption:
            await bot.edit_message_caption(
                chat_id=active_uid,
                message_id=cl_msg_id,
                caption=message.caption
            )
    except Exception as e:
        logging.error(f"Failed to sync manager edit: {e}")


# ============================================================
# CHAT MANAGEMENT
# ============================================================

async def show_chat_list(message: Message, state: FSMContext, bot: Bot):
    manager_id = message.from_user.id
    if message.text == "📊 Панель управления":
        await show_dashboard(message)
        return
    
    chats = _get_open(manager_id)
    active = _get_active(manager_id)

    if not chats:
        await message.answer("Нет открытых чатов.", parse_mode=None)
        return

    lines = ["📋 Открытые чаты:\n"]
    for uid, info in chats.items():
        name = info.get("name", "Клиент")
        username = info.get("username", "N/A")
        marker = " ← АКТИВНЫЙ" if uid == active else ""
        lines.append(f"{'🟢' if uid == active else '⚪'} {name} (@{username}) (ID: {uid}){marker}")

    lines.append(f"\nВсего: {len(chats)}")

    await message.answer(
        "\n".join(lines),
        reply_markup=get_manager_chat_kb(manager_id),
        parse_mode=None
    )


async def end_active_chat_by_manager(message: Message, state: FSMContext, bot: Bot):
    """Manager closes the currently active chat."""
    manager_id = message.from_user.id
    active_uid = _get_active(manager_id)

    if not active_uid:
        await message.answer("Нет активного чата для завершения.", parse_mode=None)
        return

    name = await _close_chat_for_client(
        manager_id, active_uid, bot, state.storage,
        notify_client=True, ended_by="manager"
    )

    chats = _get_open(manager_id)

    if chats:
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
        await state.clear()
        manager_i18n = get_i18n_for_user("ru")
        await message.answer(
            f"✅ Чат с {name} завершён. Все диалоги закрыты.\nБот снова отвечает клиентам.",
            reply_markup=get_main_menu_kb(manager_i18n),
            parse_mode=None
        )


async def end_chat_by_client(message: Message, state: FSMContext, bot: Bot):
    """Client exits the chat themselves."""
    client_id = message.from_user.id
    data = await state.get_data()
    manager_id = data.get("connected_manager_id", config.manager_id)

    # Clear client FSM and restore menu
    await state.clear()

    user_data = await get_user(client_id)
    user_lang = user_data.get("language", "ru") if user_data else "ru"
    user_i18n = get_i18n_for_user(user_lang)

    await message.answer(
        "Вы вышли из чата с менеджером.\nЕсли будут вопросы — я всегда на связи! 🎯",
        reply_markup=get_main_menu_kb(user_i18n),
        parse_mode=None
    )

    # Remove from manager's open chats
    chats = _get_open(manager_id)
    client_info = chats.pop(client_id, {})
    client_name = client_info.get("name", message.from_user.full_name or str(client_id))

    if _get_active(manager_id) == client_id:
        _set_active(manager_id, None)

    # Notify manager
    try:
        if chats:
            # Auto-switch manager to next chat
            next_uid = next(iter(chats))
            # We need manager's FSM context
            manager_ctx = await get_user_fsm(bot, state.storage, manager_id)
            next_name = await _activate_chat(manager_id, next_uid, bot, manager_ctx, state.storage)
            await bot.send_message(
                manager_id,
                f"📤 Клиент {client_name} вышел из чата.\n"
                f"🔀 Автопереключение на {next_name} (ID: {next_uid}).\n"
                f"Открыто чатов: {len(chats)}",
                reply_markup=get_manager_chat_kb(manager_id),
                parse_mode=None
            )
        else:
            # No more chats — clear manager state
            manager_ctx = await get_user_fsm(bot, state.storage, manager_id)
            await manager_ctx.clear()
            manager_i18n = get_i18n_for_user("ru")
            await bot.send_message(
                manager_id,
                f"📤 Клиент {client_name} вышел из чата. Все диалоги закрыты.\n"
                f"Бот снова отвечает клиентам.",
                reply_markup=get_main_menu_kb(manager_i18n),
                parse_mode=None
            )
    except Exception as e:
        logging.error(f"Failed to notify manager about client disconnect: {e}")


async def end_all_chats(message: Message, state: FSMContext, bot: Bot):
    """Close ALL open chats (manager presses /start)."""
    manager_id = message.from_user.id
    chats = _get_open(manager_id)

    for uid in list(chats.keys()):
        await _close_chat_for_client(
            manager_id, uid, bot, state.storage,
            notify_client=True, ended_by="manager"
        )

    open_chats.pop(manager_id, None)
    active_chat.pop(manager_id, None)
    await state.clear()

    manager_i18n = get_i18n_for_user("ru")
    await message.answer(
        "Все диалоги завершены. Бот снова отвечает клиентам.",
        reply_markup=get_main_menu_kb(manager_i18n),
        parse_mode=None
    )


async def show_dashboard(message: Message):
    """Main dashboard entry."""
    active_count = await get_active_sessions_count()
    closed_today = await get_closed_sessions_today()
    
    text = (
        "<b>📊 Панель управления менеджера</b>\n\n"
        f"🟢 Активных диалогов: {active_count}\n"
        f"✅ Завершено сегодня: {len(closed_today)}\n\n"
        "Выберите раздел для деталей 👇"
    )
    await message.answer(text, reply_markup=get_dashboard_inline_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("dash:"))
async def process_dashboard_callback(callback: CallbackQuery, bot: Bot):
    action = callback.data.split(":")[1]
    
    if action == "refresh":
        active_count = await get_active_sessions_count()
        closed_today = await get_closed_sessions_today()
        text = (
            "<b>📊 Панель управления менеджера</b>\n\n"
            f"🟢 Активных диалогов: {active_count}\n"
            f"✅ Завершено сегодня: {len(closed_today)}\n\n"
            "Обновлено ✅"
        )
        try:
            await callback.message.edit_text(text, reply_markup=get_dashboard_inline_kb(), parse_mode="HTML")
        except Exception:
            pass
        await callback.answer()
        
    elif action == "active":
        manager_id = callback.from_user.id
        chats = _get_open(manager_id)
        if not chats:
            await callback.answer("Нет активных чатов в оперативной памяти.", show_alert=True)
            return
        
        lines = ["<b>🟢 Список активных чатов:</b>\n"]
        for uid, info in chats.items():
            name = info.get("name", "Клиент")
            username = info.get("username", "N/A")
            # Replace special chars that might break HTML
            name = name.replace("<", "&lt;").replace(">", "&gt;")
            lines.append(f"👤 {name} (@{username}) [ID: {uid}]")
        
        await callback.message.answer("\n".join(lines), parse_mode="HTML")
        await callback.answer()

    elif action == "finished":
        closed = await get_closed_sessions_today()
        if not closed:
            await callback.answer("Сегодня ещё нет завершённых чатов.", show_alert=True)
            return
            
        lines = ["<b>✅ Завершённые сегодня:</b>\n"]
        for sess, name in closed:
            time_str = sess.ended_at.strftime("%H:%M")
            safe_name = (name or "Клиент").replace("<", "&lt;").replace(">", "&gt;")
            lines.append(f"🏁 {time_str} — {safe_name} [ID: {sess.user_id}]")
        
        lines.append(f"\nВсего: {len(closed)}")
        
        clear_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Удалить список", callback_data="dash:clear_finished")],
            [InlineKeyboardButton(text="🔙 Назad", callback_data="dash:refresh")]
        ])
            
        await callback.message.answer("\n".join(lines), reply_markup=clear_kb, parse_mode="HTML")
        await callback.answer()

    elif action == "requests":
        pending = await get_pending_requests()
        if not pending:
            await callback.answer("Нет ожидающих запросов.", show_alert=True)
            return
        
        lines = ["<b>🔔 Ожidающие запросы:</b>\n"]
        for req in pending[:20]:  # max 20
            safe_name = (req.user_name or "Клиент").replace("<", "&lt;").replace(">", "&gt;")
            time_str = req.created_at.strftime("%H:%M") if req.created_at else "?"
            type_emoji = {"lead": "📋", "manager_request": "🙋", "form_incomplete": "⚠️"}.get(req.request_type, "📩")
            preview = ""
            if req.message_preview:
                preview = f"\n   💬 {req.message_preview[:80]}..."
            lines.append(f"{type_emoji} {time_str} — {safe_name} (@{req.username or 'N/A'}) [ID: {req.user_id}]{preview}")
        
        lines.append(f"\nВсего: {len(pending)}")
        
        # Add accept buttons for each pending request
        buttons = []
        for req in pending[:10]:
            safe_name = (req.user_name or "Клиент")[:30]
            buttons.append([InlineKeyboardButton(
                text=f"✅ Принять: {safe_name}",
                callback_data=f"accept_chat:{req.user_id}"
            )])
        buttons.append([InlineKeyboardButton(text="🔙 Назad", callback_data="dash:refresh")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.answer("\n".join(lines), reply_markup=kb, parse_mode="HTML")
        await callback.answer()

    elif action == "reset_all":
        # Reset ALL active chats — both manager and all clients get notified
        manager_id = callback.from_user.id
        chats = _get_open(manager_id)
        
        if not chats:
            await callback.answer("Нет активных чатов для сброса.", show_alert=True)
            return

        count = len(chats)
        
        # Close each chat — notify clients
        for uid in list(chats.keys()):
            try:
                # Clear client FSM
                user_ctx = await get_user_fsm(bot, bot.session, uid)
            except Exception:
                pass
            
            # Notify client
            user_data = await get_user(uid)
            user_lang = user_data.get("language", "ru") if user_data else "ru"
            user_i18n = get_i18n_for_user(user_lang)
            try:
                await bot.send_message(
                    uid,
                    "Менеджер завершил диалог. Если будут вопросы — я всегда на связи! 🎯",
                    reply_markup=get_main_menu_kb(user_i18n),
                    parse_mode=None
                )
            except Exception:
                pass
            
            # End DB session
            await end_chat_session(uid)
        
        # Clear all in-memory state
        open_chats.pop(manager_id, None)
        active_chat.pop(manager_id, None)
        await clear_all_pending_requests()
        
        manager_i18n = get_i18n_for_user("ru")
        await callback.message.answer(
            f"🚨 Сброшено {count} чатов. Все диалоги закрыты.\n"
            f"Бот снова отвечает клиентам.",
            reply_markup=get_main_menu_kb(manager_i18n),
            parse_mode=None
        )
        await callback.answer("Все чаты сброшены!")

    elif action == "clear_finished":
        await clear_finished_sessions_today()
        await callback.answer("Список завершённых очищен!", show_alert=True)
        # Refresh dashboard
        active_count = await get_active_sessions_count()
        text = (
            "<b>📊 Панель управления менеджера</b>\n\n"
            f"🟢 Активных диалогов: {active_count}\n"
            f"✅ Завершено сегодня: 0\n\n"
            "Список очищен ✅"
        )
        try:
            await callback.message.edit_text(text, reply_markup=get_dashboard_inline_kb(), parse_mode="HTML")
        except Exception:
            pass


# ============================================================
# STALE EXIT BUTTONS — when chat already ended but button still visible
# This MUST be at the bottom so ManagerChat.in_chat handler gets priority
# ============================================================

@router.message(F.text.in_([
    "❌ Завершить чат",
    "❌ Завершить диалог / Ավարտել",
    "Завершить чат",
    "Завершить диалог",
    "Ավարտել",
]))
async def stale_end_chat_button(message: Message, i18n, state: FSMContext):
    """Catch exit button presses when user is NOT in ManagerChat.in_chat state.
    This means the chat was already ended (by manager or system).
    Just clear state and show the normal main menu."""
    await state.clear()
    await message.answer(
        i18n("main_menu"),
        reply_markup=get_main_menu_kb(i18n),
        parse_mode=None
    )
