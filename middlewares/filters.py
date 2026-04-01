from aiogram.filters import Filter
from aiogram.types import Message
from typing import Union, Dict, Any, Callable
from .i18n import i18n_manager

class I18nTextFilter(Filter):
    def __init__(self, key: str):
        self.key = key

    async def __call__(self, message: Message, language: str) -> bool:
        # Get translation for current user language
        translation = i18n_manager.get(self.key, language)
        return message.text == translation
