import os
from typing import List, Dict, Any, Optional
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class LLMProvider:
    """Base class for LLM providers."""
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

class MockLLM(LLMProvider):
    """Mock LLM for testing without API keys."""
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        logger.info("Using Mock LLM")
        # Extract the question from the prompt (it's at the end)
        question = user_prompt.split("Question:")[-1].lower() if "Question:" in user_prompt else user_prompt.lower()
        logger.info(f"MockLLM extracted question: {question}")
        
        if "expense ratio" in question:
            return "The expense ratio for this fund is 0.81%. \nSource: https://www.hdfcfund.com/factsheet"
        if "exit load" in question:
            return "The exit load is 1% if redeemed within 1 year. \nSource: https://www.hdfcfund.com/sid"
        if "should i" in question or "invest" in question:
            return "I am sorry, but I cannot provide investment advice. Please consult a financial advisor."
        if "phone number" in question or "exist" in question:
            return "I do not have enough information in the provided context to answer that. \nSource: https://www.hdfcfund.com/unknown"
        
        return "I am sorry, but I do not have enough information in the provided context."

class GroqProvider(LLMProvider):
    """Groq implementation."""
    def __init__(self, api_key: str, model: str = "llama-3.1-8b-instant"):
        from groq import Groq
        self.client = Groq(api_key=api_key)
        self.model = model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0
        )
        return response.choices[0].message.content

class OpenAIProvider(LLMProvider):
    """OpenAI implementation."""
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0
        )
        return response.choices[0].message.content

def get_llm_provider() -> LLMProvider:
    """Factory to get the appropriate LLM provider. Groq is mandatory for production use."""
    groq_api_key = os.getenv("GROQ_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if groq_api_key:
        logger.info("Groq API Key found. Using GroqProvider.")
        return GroqProvider(groq_api_key)
    elif openai_api_key:
        logger.info("OpenAI API Key found. Using OpenAIProvider.")
        return OpenAIProvider(openai_api_key)
    else:
        logger.error("No LLM API Key found. Production requires GROQ_API_KEY.")
        raise ValueError("Missing GROQ_API_KEY. Please set it in your .env file.")
