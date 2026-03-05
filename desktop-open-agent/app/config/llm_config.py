"""LLM 模型配置"""
from langchain_openai import ChatOpenAI
from app.config.settings import settings

model = ChatOpenAI(
    model=settings.llm_model,
    temperature=settings.llm_temperature,
    max_tokens=settings.llm_max_tokens,
    api_key=settings.dashscope_api_key,
    base_url=settings.dashscope_api_url,
    streaming=True,
    model_kwargs={"parallel_tool_calls": True},
)
