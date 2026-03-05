"""全局配置"""
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent.parent
ROOT_DIR = BASE_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM
    dashscope_api_key: str = Field(description="百炼 API Key")
    dashscope_api_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="百炼 API URL",
    )

    # 模型
    llm_model: str = Field(default="qwen-plus")
    llm_temperature: float = Field(default=0.3)
    llm_max_tokens: int = Field(default=2048)

    # 应用
    app_name: str = Field(default="Desktop Open Agent")
    app_version: str = Field(default="1.0.0")
    debug: bool = Field(default=True)
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)


settings = Settings()
