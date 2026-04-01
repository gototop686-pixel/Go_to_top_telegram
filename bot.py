import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperty

from config.config import config
from database.models import init_db
from middlewares.i18n import I18nMiddleware
from handlers import common, ai_support, sales_funnel

async def main():
    # Initialize database
    await init_db()
    
    # Initialize bot and dispatcher
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperty(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Register middleware
    dp.message.middleware(I18nMiddleware())
    dp.callback_query.middleware(I18nMiddleware())

    # Register routers
    dp.include_router(common.router)
    dp.include_router(sales_funnel.router)
    dp.include_router(ai_support.router)

    # Logging
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")
