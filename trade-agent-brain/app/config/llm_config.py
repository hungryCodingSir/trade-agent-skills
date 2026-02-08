"""LLM 模型配置: 主模型 / 轻量模型 / Embedding"""
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from app.config.settings import settings

main_model = ChatOpenAI(
    model=settings.llm_model,
    temperature=settings.llm_temperature,
    max_tokens=settings.llm_max_tokens,
    api_key=settings.dashscope_api_key,
    base_url=settings.dashscope_api_url,
)

mini_model = ChatOpenAI(
    model=settings.mini_llm_model,
    temperature=settings.mini_llm_temperature,
    api_key=settings.dashscope_api_key,
    base_url=settings.dashscope_api_url,
)

embedding_model = OpenAIEmbeddings(
    api_key=settings.dashscope_api_key,
    base_url=settings.dashscope_api_url,
    model=settings.embedding_model,
    dimensions=1024,
    check_embedding_ctx_length=False,
)
