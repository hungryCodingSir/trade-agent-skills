"""MySQL 数据库连接"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import contextmanager
from app.config.settings import settings
from loguru import logger

DATABASE_URL = (
    f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}"
    f"@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}"
    f"?charset=utf8mb4"
)

engine = create_engine(
    DATABASE_URL,
    pool_size=settings.mysql_pool_size,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@contextmanager
def get_db_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def check_mysql_connection() -> bool:
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
            logger.info("MySQL connection OK")
            return True
    except Exception as e:
        logger.error(f"MySQL connection failed: {e}")
        return False
