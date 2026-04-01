import os
from google import genai
from google.genai import types
from config.config import config

# This is the specialized knowledge base for GO to Top WB
KNOWLEDGE_BASE = """
Компания: GO to Top WB — сервис продвижения на Wildberries.

ОСНОВНОЙ ПРОЦЕСС:
Входящий запрос → Сбор данных → Расчет и PDF → Оплата → Рабочая группа (WhatsApp) → Техническое Задание (ТЗ) → Запуск → Склад и доставка.

ПРАВИЛА ОБЩЕНИЯ (КРИТИЧЕСКИ ВАЖНО):
1. Тон: Теплый и деловой, умеренное использование эмодзи.
2. НИКОГДА не гарантировать выход в ТОП. Алгоритмы WB вне нашего контроля, но мы максимизируем шансы через безопасные методы.
3. НИКОГДА не раскрывать внутреннюю механику работы (это наше конкурентное преимущество).
4. НИКОГДА не называть финальную цену без получения артикула и объема закупок.
5. Если клиент просит "просто цену" — отправить к прайс-листу (упомянуть, что он на сайте) и запросить данные для точного расчета.
6. В конце любого ответа — предложение сделать расчет (CTA).

УСЛУГИ И ПРЕИМУЩЕСТВА:
- Целевые самовыкупы (имитация реального поведения покупателя: просмотр, сравнение, корзина, паузы).
- Реальные аккаунты и физические устройства.
- Свои склады и логистика (забор из ПВЗ, хранение, доставка на склад WB в Ереване).
- Формирование ТЗ в Google Sheets для точности.
- Аналитика и рост органических продаж за счет улучшения CTR и веса карточки.

ЛОГИСТИКА:
- Доставка на склад WB 3 раза в неделю: Понедельник, Четверг, Суббота.
- Хранение: первые 3 дня бесплатно, далее 500 драм/день за коробку.

ОПЛАТА:
- Расчетный счет (+6%), Карта (+2%), Cash Out Ameria (0%), Telcell/Idram (0%).

КОНТАКТЫ:
Сайт: https://gototopwb.ru
"""

import os
import asyncio
from google import genai
from google.genai import types
from config.config import config

# ... (KNOWLEDGE_BASE content) ...

class AIService:
    def __init__(self):
        self.client = genai.Client(api_key=config.gemini_api_key)
        self.model_name = "gemini-1.5-flash"

    async def get_answer(self, question: str, language: str = "ru") -> str:
        prompt = f"""
        Ты — ассистент службы продвижения на Wildberries.
        Общайся на языке: {language}.
        
        Твоя база знаний:
        {KNOWLEDGE_BASE}
        
        Вопрос пользователя: {question}
        
        Инструкции:
        - Использовать ТОЛЬКО базу знаний.
        - Ничего не придумывать.
        - Использовать мягкий призыв к действию (CTA): предложить расчет.
        """
        
        try:
            # Wrap the synchronous library call in a thread
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=500
                )
            )
            if not response.text:
                 raise ValueError("AI returned empty response")
            return response.text
        except Exception as e:
            logging.error(f"AI ERROR: {str(e)}")
            # In MVP/Debug mode, we return the error to the user for faster troubleshooting
            return f"Ошибка ИИ: {str(e)}. Пожалуйста, убедитесь, что GEMINI_API_KEY верен."

ai_service = AIService()
