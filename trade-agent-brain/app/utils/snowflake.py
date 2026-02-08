"""雪花算法 ID 生成器"""
from snowflake import SnowflakeGenerator

_generator = SnowflakeGenerator(instance=1)


def generate_id() -> int:
    return next(_generator)
