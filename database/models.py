from datetime import datetime
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config.config import config

# Create async engine
engine = create_async_engine(config.async_database_url, echo=False)

# Create session maker
async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    user_id = Column(BigInteger, primary_key=True)
    language = Column(String(5), default="ru")
    name = Column(String(255))
    wb_article = Column(String(255))
    box_qty = Column(Integer)
    planned_qty = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class Interaction(Base):
    __tablename__ = "interactions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"))
    mode = Column(String(50)) # 'funnel' or 'ai'
    state = Column(String(100))
    bot_response = Column(Text)
    user_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
