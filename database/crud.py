from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict

from .models import User, Interaction, MessageMap, ChatSession, ChatRequest, async_session
from datetime import datetime, timedelta

async def get_user_full(user_id: int):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        return result.scalar_one_or_none()

async def map_message(m_chat_id: int, m_msg_id: int, c_chat_id: int, c_msg_id: int):
    async with async_session() as session:
        mapping = MessageMap(
            manager_chat_id=m_chat_id,
            manager_msg_id=m_msg_id,
            client_chat_id=c_chat_id,
            client_msg_id=c_msg_id
        )
        session.add(mapping)
        await session.commit()

async def get_client_msg_id(m_chat_id: int, m_msg_id: int) -> Optional[int]:
    async with async_session() as session:
        result = await session.execute(
            select(MessageMap.client_msg_id)
            .where(MessageMap.manager_chat_id == m_chat_id)
            .where(MessageMap.manager_msg_id == m_msg_id)
        )
        return result.scalar()

async def start_chat_session(user_id: int, manager_id: int):
    async with async_session() as session:
        new_session = ChatSession(user_id=user_id, manager_id=manager_id)
        session.add(new_session)
        await session.commit()

async def end_chat_session(user_id: int):
    async with async_session() as session:
        await session.execute(
            update(ChatSession)
            .where(ChatSession.user_id == user_id)
            .where(ChatSession.status == "active")
            .values(status="closed", ended_at=datetime.utcnow())
        )
        await session.commit()

async def get_active_sessions_count() -> int:
    async with async_session() as session:
        result = await session.execute(
            select(ChatSession)
            .where(ChatSession.status == "active")
        )
        return len(result.all())

async def get_closed_sessions_today() -> list:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    async with async_session() as session:
        result = await session.execute(
            select(ChatSession, User.name)
            .join(User, ChatSession.user_id == User.user_id)
            .where(ChatSession.status == "closed")
            .where(ChatSession.ended_at >= today_start)
        )
        return result.all()

async def save_chat_request(user_id: int, user_name: str, username: str,
                            request_type: str, message_preview: str = ""):
    """Save a pending chat request when client asks for manager."""
    async with async_session() as session:
        req = ChatRequest(
            user_id=user_id,
            user_name=user_name,
            username=username,
            request_type=request_type,
            message_preview=message_preview[:500] if message_preview else ""
        )
        session.add(req)
        await session.commit()


async def get_pending_requests() -> list:
    """Get all pending (unaccepted) chat requests."""
    async with async_session() as session:
        result = await session.execute(
            select(ChatRequest)
            .where(ChatRequest.status == "pending")
            .order_by(ChatRequest.created_at.desc())
        )
        return result.scalars().all()


async def accept_chat_request(user_id: int):
    """Mark chat requests from this user as accepted."""
    async with async_session() as session:
        await session.execute(
            update(ChatRequest)
            .where(ChatRequest.user_id == user_id)
            .where(ChatRequest.status == "pending")
            .values(status="accepted")
        )
        await session.commit()


async def clear_finished_sessions_today():
    """Delete all finished chat sessions from today."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    async with async_session() as session:
        from sqlalchemy import delete
        await session.execute(
            delete(ChatSession)
            .where(ChatSession.status == "closed")
            .where(ChatSession.ended_at >= today_start)
        )
        await session.commit()


async def clear_all_pending_requests():
    """Delete all pending chat requests."""
    async with async_session() as session:
        from sqlalchemy import delete
        await session.execute(
            delete(ChatRequest)
            .where(ChatRequest.status == "pending")
        )
        await session.commit()


async def get_user(user_id: int) -> Optional[Dict]:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        if user:
            return {
                "user_id": user.user_id,
                "language": user.language,
                "name": user.name,
                "wb_article": user.wb_article,
                "box_qty": user.box_qty,
                "planned_qty": user.planned_qty
            }
        return None

async def save_user(user_id: int, username: Optional[str] = None, full_name: Optional[str] = None):
    """Saves or updates basic user info on /start."""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(user_id=user_id, name=full_name)
            session.add(user)
        else:
            user.name = full_name
            
        await session.commit()

async def create_user(user_id: int, language: str = 'ru'):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        if not result.scalar_one_or_none():
            new_user = User(user_id=user_id, language=language)
            session.add(new_user)
            await session.commit()

async def update_user_language(user_id: int, language: str):
    async with async_session() as session:
        await session.execute(
            update(User).where(User.user_id == user_id).values(language=language)
        )
        await session.commit()

async def update_user_data(user_id: int, data: dict):
    if not data:
        return
    
    async with async_session() as session:
        # Check if 'article' should map to 'wb_article'
        if 'article' in data:
            data['wb_article'] = data.pop('article')
            
        await session.execute(
            update(User).where(User.user_id == user_id).values(**data)
        )
        await session.commit()

async def log_interaction(user_id: int, mode: str, state: str, user_message: str, bot_response: str):
    async with async_session() as session:
        interaction = Interaction(
            user_id=user_id,
            mode=mode,
            state=state,
            user_message=user_message,
            bot_response=bot_response
        )
        session.add(interaction)
        await session.commit()
