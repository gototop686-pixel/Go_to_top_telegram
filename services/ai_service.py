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
import logging
from google import genai
from google.genai import types
from config.config import config

# ... (KNOWLEDGE_BASE content) ...

class AIService:
    def __init__(self):
        try:
            self.client = genai.Client(api_key=config.gemini_api_key)
            self.models_to_try = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-flash-8b"]
            self.model_name = self.models_to_try[0]
            logging.info(f"AI Service initialized with models: {self.models_to_try}")
        except Exception as e:
            logging.error(f"Failed to initialize AI Service: {e}")

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
        
        for model in self.models_to_try:
            try:
                logging.info(f"Asking AI using model: {model}")
                # Add a strict timeout
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.models.generate_content,
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.3,
                            max_output_tokens=300
                        )
                    ),
                    timeout=15.0
                )
                
                if response and response.text:
                    # Successfully got response, update preferred model if it's different
                    if self.model_name != model:
                        self.model_name = model
                    return response.text
                
            except (asyncio.TimeoutError, Exception) as e:
                err_msg = str(e).upper()
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    logging.warning(f"Model {model} exhausted (429). Trying next...")
                    continue
                elif "404" in err_msg or "NOT_FOUND" in err_msg:
                    logging.warning(f"Model {model} not found (404). Trying next...")
                    continue
                else:
                    logging.error(f"Unexpected AI Error with {model}: {e}")
                    # Try next model anyway for stability
                    continue
        
        # If all models failed
        return "ИИ временно недоступен из-за ограничений квот. Пожалуйста, обратитесь к менеджеру."

ai_service = AIService()

ai_service = AIService()
