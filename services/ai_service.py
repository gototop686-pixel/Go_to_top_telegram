import asyncio
import logging
import re
import json
from collections import defaultdict
from openai import AsyncOpenAI
from config.config import config

# Load system prompt - try local file first, then fallback
import os

SYSTEM_PROMPT = ""

# Try loading from project directory (for deployment)
_prompt_paths = [
    os.path.join(os.path.dirname(__file__), "system_prompt.md"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "services", "system_prompt.md"),
    "/home/work/.openclaw/workspace/liya_prompt_v4_final.md",
]

for _path in _prompt_paths:
    if os.path.exists(_path):
        with open(_path, "r", encoding="utf-8") as _f:
            SYSTEM_PROMPT = _f.read()
        break

if not SYSTEM_PROMPT:
    SYSTEM_PROMPT = """Ты — Лия, AI-ассистент компании Go to Top. Помогаешь клиентам с продвижением товаров на Wildberries через самовыкупы. Отвечай кратко, по делу, на языке клиента (русский или армянский). Не используй звёздочки и markdown."""


class ConversationHistory:
    """Stores conversation history per user for context-aware responses."""
    
    def __init__(self, max_messages: int = 12):
        self.histories = defaultdict(list)
        self.max_messages = max_messages
    
    def add_user_message(self, user_id: int, message: str):
        self.histories[user_id].append({"role": "user", "content": message})
        self._trim(user_id)
    
    def add_assistant_message(self, user_id: int, message: str):
        self.histories[user_id].append({"role": "assistant", "content": message})
        self._trim(user_id)
    
    def get_messages(self, user_id: int) -> list:
        return list(self.histories[user_id])
    
    def clear(self, user_id: int):
        self.histories[user_id] = []
    
    def _trim(self, user_id: int):
        if len(self.histories[user_id]) > self.max_messages:
            self.histories[user_id] = self.histories[user_id][-self.max_messages:]


def parse_lead_ready(response: str):
    """Extract [LEAD_READY] JSON from AI response if present."""
    match = re.search(r'\[LEAD_READY\](.*?)\[/LEAD_READY\]', response, re.DOTALL)
    if match:
        clean_response = response[:match.start()].strip()
        try:
            lead_data = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            lead_data = {"raw": match.group(1).strip()}
        return clean_response, lead_data
    return response, None


class AIService:
    def __init__(self):
        self.keys = config.groq_keys
        self.clients = [
            AsyncOpenAI(api_key=k, base_url="https://api.groq.com/openai/v1")
            for k in self.keys
        ]
        
        self.models_to_try = [
            "llama-3.3-70b-versatile",
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
        ]
        
        self.conversation = ConversationHistory(max_messages=12)
        
        logging.info(f"AI Service (Liya) initialized with {len(self.keys)} API keys.")

    async def get_answer(self, question: str, language: str = "ru", user_id: int = 0) -> str:
        lang_str = "Русский (Russian)" if language == "ru" else "Հայերեն (Armenian)"
        
        formatted_prompt = SYSTEM_PROMPT.replace("{manager_id}", str(config.manager_id))
        
        # Add user message to history
        self.conversation.add_user_message(user_id, question)
        
        # Build messages: system + history
        messages = [
            {"role": "system", "content": formatted_prompt + f"\n\nТЕКУЩИЙ ЯЗЫК ОБЩЕНИЯ: {lang_str}"}
        ]
        messages.extend(self.conversation.get_messages(user_id))
        
        # Try each key and model
        for i, client in enumerate(self.clients):
            for model in self.models_to_try:
                try:
                    logging.info(f"Liya: Key {i+1}/{len(self.keys)}, model {model}, lang {lang_str}")
                    
                    response = await asyncio.wait_for(
                        client.chat.completions.create(
                            model=model,
                            messages=messages,
                            temperature=0.5,
                            max_tokens=1500
                        ),
                        timeout=30.0
                    )
                    
                    if response and response.choices:
                        answer = response.choices[0].message.content
                        
                        # Parse and remove [LEAD_READY] tag if present
                        clean_answer, lead_data = parse_lead_ready(answer)
                        
                        # Store clean response in history
                        self.conversation.add_assistant_message(user_id, clean_answer)
                        
                        # Return with lead_data flag (handled by caller)
                        if lead_data:
                            return f"{clean_answer}\n[LEAD_DATA]{json.dumps(lead_data, ensure_ascii=False)}[/LEAD_DATA]"
                        
                        return clean_answer
                        
                except asyncio.TimeoutError:
                    logging.warning(f"Timeout on Key {i+1}, Model {model}")
                    continue
                except Exception as e:
                    msg = str(e).lower()
                    if "429" in msg or "413" in msg:
                        logging.warning(f"Key {i+1} rate limited on {model}")
                        break
                    elif "decommissioned" in msg:
                        logging.warning(f"Model {model} decommissioned")
                        continue
                    else:
                        logging.error(f"Error Key {i+1}, Model {model}: {e}")
                        continue
        
        return "Извините, я временно не могу ответить. Пожалуйста, обратитесь к менеджеру через кнопку ниже 👱‍♀️"

    def clear_history(self, user_id: int):
        self.conversation.clear(user_id)


ai_service = AIService()
