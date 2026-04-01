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
ПОДРОБНЫЕ УСЛУГИ:
- Самовыкупы: Полная имитация живого клиента (поиск по ключам, сравнение, добавление в корзину, паузы, покупка). 100% защита от бана.
- Отзывы: Только от реальных пользователей с историей покупок. Повышаем вес карточки и рейтинг.
- Логистика: Забор товара из ПВЗ, хранение на нашем складе (Ереван), доставка на Склад WB 3 раза в неделю (Пн, Чт, Сб).
- Цена: Мы не берем фиксированную плату "за воздух". Цена зависит от сложности ниши и объема. Наш калькулятор на сайте дает примерный ориентир, а менеджер — точный расчет в PDF.

ВАЖНЫЕ ПРАВИЛА (SCRIPT):
- Тон: Теплый, но строго деловой. Ты — лицо компании.
- Язык: Если клиент пишет на армянском, отвечай на развернутом и профессиональном армянском (հայերեն). Ответы на армянском ДОЛЖНЫ быть такими же качественными и длинными, как на русском.
- Safety: Мы гарантируем БЕЗОПАСНАЯ работа. Мы рискуем своим товаром так же, как и клиент.
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
        Ты — высококвалифицированный эксперт компании GO TO TOP по продвижению товаров на Wildberries. 
        Твоё общение должно быть максимально профессиональным, теплым и деловым. Ты — не просто бот, ты бизнес-партнер.

        Язык диалога: {language}.

        Твоя база знаний (Script & Strategy):
        {KNOWLEDGE_BASE}

        ИНСТРУКЦИЯ ПО СТИЛЮ (ЖЕСТКО):
        1. БЕЗ ПРИВЕТСТВИЙ: Сразу отвечай на вопрос. Никаких "Привет", "Բարև", "Здравствуйте". 
        2. ЭКСПЕРТНОСТЬ: Давай глубокие, развернутые ответы. Если клиент спрашивает цену — объясни, почему она индивидуальна и что в неё входит (логистика, склады, безопасность).
        3. СТРУКТУРА: Используй много тематических эмодзи (📈, 🚀, 🛡️, 💎, 📑), списки и абзацы. Текст должен быть визуально приятным и легким для чтения.
        4. ДОВЕРИЕ: Акцентируй внимание на нашей безопасности. Мы не используем "серые" схемы, наши самовыкупы имитируют реальный путь клиента, что исключает бан.
        5. ВОРОНКА: Если клиент проявляет интерес к сотрудничеству (например, спрашивает "как начать" или "сколько стоит"), вежливо напомни, что лучший первый шаг — это расчет стоимости (кнопка ниже), чтобы мы подготовили для него PDF.

        Вопрос пользователя: {question}
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
                            max_output_tokens=1000
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
