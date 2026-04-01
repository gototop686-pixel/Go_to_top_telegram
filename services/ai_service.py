import os
import asyncio
import logging
from google import genai
from google.genai import types
from config.config import config

# This is the specialized knowledge base for GO to Top WB
KNOWLEDGE_BASE = """
Компания: GO TO TOP
Специализация: Продвижение на Wildberries через безопасные самовыкупы, отзывы и аналитику.

ОСНОВНОЙ ПРОЦЕСС:
1. Запрос от клиента -> 2. Сбор данных (Артикул, Количество) -> 3. Расчет стоимости и PDF -> 4. Оплата -> 5. Создание рабочей группы -> 6. Составление ТЗ -> 7. Запуск в работу -> 8. Складская логистика.

УСЛУГИ:
- Реальные самовыкупы (имитация поведения живого покупателя).
- Написание отзывов от реальных пользователей.
- Работа с рейтингом товара.
- Аналитика органических продаж.
- Свои склады и логистика (забор из ПВЗ, доставка на склады WB в Ереване).

ЛОГИСТИКА:
- Отгрузка 3 раза в неделю: Понедельник, Четверг, Суббота.
- Хранение на нашем складе: первые 3 дня БЕСПЛАТНО, далее 500 драм/день за коробку.

ВАЖНЫЕ ПРАВИЛА:
- Мягкий и деловой стиль общения.
- НИКОГДА не гарантировать 100% выход в ТОП (это невозможно из-за алгоритмов WB), но мы обеспечиваем рост показателей.
- НИКОГДА не раскрывать внутренние технические механики работы.
- Оплата: Р/С (+6%), Карта (+2%), Idram/Telcell (0%).

Сайт: https://gototopwb.ru
"""

class AIService:
    def __init__(self):
        try:
            self.client = genai.Client(api_key=config.gemini_api_key)
            # 2026 standard flagship models
            self.models_to_try = [
                "gemini-3-flash", 
                "gemini-2.5-flash", 
                "gemini-2.0-flash", 
                "gemini-1.5-flash"
            ]
            self.model_name = self.models_to_try[0]
            logging.info(f"AI Service initialized with latest models: {self.models_to_try}")
        except Exception as e:
            logging.error(f"Failed to initialize AI Service: {e}")

    async def get_answer(self, question: str, language: str = "ru") -> str:
        prompt = f"""
        Ты — профессиональный менеджер-консультант компании GO TO TOP.
        Твоя задача: вежливо и четко отвечать на вопросы о наших услугах по продвижению на Wildberries.

        Общайся на языке пользователя (по умолчанию: {language}).

        Твоя база знаний:
        {KNOWLEDGE_BASE}

        ПРАВИЛА ОТВЕТА:
        - Будь честен: не обещай "гарантированный ТОП", но подчеркивай безопасность и эффективность наших методов.
        - Ответ должен быть кратким (не более 3-4 предложений), профессиональным и емким.
        - Используй ТОЛЬКО информацию из базы знаний. Не придумывай лишнего.
        - НЕ предлагай расчет в каждом сообщении. Твоя цель сейчас — просто качественно ответить на вопрос.
        - Тон общения: вежливый, экспертный, доброжелательный.
        - Вопрос пользователя: {question}
        """
        
        for model in self.models_to_try:
            try:
                logging.info(f"Asking AI using model: {model}")
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.models.generate_content,
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.3,
                            max_output_tokens=400
                        )
                    ),
                    timeout=15.0
                )
                
                if response and response.text:
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
                    continue
        
        return "Извините, сейчас я не могу ответить. Пожалуйста, обратитесь к менеджеру напрямую."

ai_service = AIService()
