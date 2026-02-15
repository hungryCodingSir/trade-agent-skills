"""全局配置"""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM
    dashscope_api_key: str = Field(description="百炼 API Key")
    dashscope_api_url: str = Field(description="百炼 API URL")

    # 应用
    app_name: str = Field(default="Trade Agent Brain")
    app_version: str = Field(default="2.0.0")
    debug: bool = Field(default=True)

    # 主模型
    llm_model: str = Field(default="qwen-plus")
    llm_temperature: float = Field(default=0.3)
    llm_max_tokens: int = Field(default=4096)

    # 轻量模型（摘要/规划）
    mini_llm_model: str = Field(default="qwen-turbo")
    mini_llm_temperature: float = Field(default=0.1)

    # Embedding
    embedding_model: str = Field(default="text-embedding-v4")

    # Agent
    agent_max_tokens_before_summary: int = Field(default=4000)
    agent_messages_to_trigger: int = Field(default=10)
    agent_messages_to_keep: int = Field(default=4)
    skills_dir: str = Field(default="./skills/")

    @property
    def skills_dir_absolute(self) -> Path:
        """返回 skills 目录的绝对路径"""
        skills_path = Path(self.skills_dir)
        if skills_path.is_absolute():
            return skills_path
        return BASE_DIR / self.skills_dir

    # MySQL
    mysql_host: str = Field(default="127.0.0.1")
    mysql_port: int = Field(default=3306)
    mysql_user: str = Field(default="root")
    mysql_password: str = Field(default="")
    mysql_database: str = Field(default="trade_agent")
    mysql_pool_size: int = Field(default=10)

    # Redis
    redis_host: str = Field(default="127.0.0.1")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Milvus
    milvus_host: str = Field(default="127.0.0.1")
    milvus_port: int = Field(default=19530)

    # MCP
    mcp_server_url: str = Field(default="http://127.0.0.1:9001/sse")
    mcp_call_timeout: int = Field(default=30)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


load_dotenv()
settings = get_settings()
