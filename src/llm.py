"""Language model layer, provider-agnostic through LangChain.

LangChain is used only here: its chat model integrations share one interface, so
switching between a free cloud tier (Gemini, Groq) and a local model (Ollama)
is a matter of configuration. Retrieval stays explicit in src/retriever.py.

Configuration (environment variables or a .env file):
- LLM_PROVIDER: gemini (default) | groq | ollama
- LLM_MODEL: optional, overrides the provider default
- GOOGLE_API_KEY / GROQ_API_KEY: credentials for the cloud providers
- OLLAMA_BASE_URL: optional, defaults to http://localhost:11434
"""

import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODELS = {
    "gemini": "gemini-flash-lite-latest",
    "groq": "openai/gpt-oss-120b",
    "ollama": "llama3.1:8b",
}
REQUIRED_KEYS = {"gemini": "GOOGLE_API_KEY", "groq": "GROQ_API_KEY", "ollama": None}


def provider() -> str:
  return os.getenv("LLM_PROVIDER", "gemini").strip().lower()


def model_name() -> str:
  return os.getenv("LLM_MODEL") or DEFAULT_MODELS.get(provider(), "")


def is_configured() -> bool:
  name = provider()
  if name not in DEFAULT_MODELS:
    return False
  key = REQUIRED_KEYS[name]
  if name == "gemini" and not os.getenv(key) and os.getenv("GEMINI_API_KEY"):
    os.environ[key] = os.environ["GEMINI_API_KEY"]
  return key is None or bool(os.getenv(key))


def create_chat_model(temperature: float = 0.1):
  name = provider()
  if name == "gemini":
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=model_name(), temperature=temperature)
  if name == "groq":
    from langchain_groq import ChatGroq
    return ChatGroq(model=model_name(), temperature=temperature)
  if name == "ollama":
    from langchain_ollama import ChatOllama
    return ChatOllama(
        model=model_name(),
        temperature=temperature,
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )
  raise ValueError(f"LLM_PROVIDER inválido: {name}. Use gemini, groq ou ollama.")


class LLMGenerator:

  def __init__(self, chat_model=None):
    self.chat_model = chat_model or create_chat_model()
    self.label = f"{provider()} · {model_name()}"

  def generate(self, system_prompt: str, user_prompt: str) -> str:
    from langchain_core.prompts import ChatPromptTemplate

    prompt = ChatPromptTemplate.from_messages(
        [("system", "{system}"), ("human", "{user}")]
    )
    chain = prompt | self.chat_model
    response = chain.invoke({"system": system_prompt, "user": user_prompt})
    content = response.content
    if isinstance(content, list):
      content = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return content.strip()
