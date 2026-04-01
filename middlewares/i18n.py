import json
from typing import Any, Awaitable, Callable, Dict, Union
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from database.crud import get_user, create_user

class I18nManager:
    def __init__(self):
        self.locales = {
            'ru': {},
            'am': {}
        }
        self.load_locales()

    def load_locales(self):
        with open('locales/ru.json', 'r', encoding='utf-8') as f:
            self.locales['ru'] = json.load(f)
        with open('locales/am.json', 'r', encoding='utf-8') as f:
            self.locales['am'] = json.load(f)

    def get(self, key: str, language: str = 'ru', **kwargs) -> str:
        lang_dict = self.locales.get(language, self.locales['ru'])
        text = lang_dict.get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass
        return text

i18n_manager = I18nManager()

class I18nMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any]
    ) -> Any:
        
        user_id = event.from_user.id
        user_data = await get_user(user_id)
        
        if not user_data:
            await create_user(user_id)
            language = 'ru'
        else:
            language = user_data.get('language', 'ru')

        # Inject language to handlers
        data['language'] = language
        
        # Inject the I18n getter function to handlers
        def i18n_get(key: str, **kwargs) -> str:
            return i18n_manager.get(key, language, **kwargs)
            
        data['i18n'] = i18n_get
        data['i18n_manager'] = i18n_manager

        return await handler(event, data)
