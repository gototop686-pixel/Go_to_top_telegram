from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict

from .models import User, Interaction, async_session

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
