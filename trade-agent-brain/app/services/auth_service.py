"""认证服务"""
from app.models.schemas import UserContext, UserType


async def get_current_user() -> UserContext:
    """Mock 用户，生产环境替换为 JWT Token 验证"""
    return UserContext(
        user_id=1,
        username="buyer_test",
        user_type=UserType.BUYER,
        company_name="Test Buyer Co.",
        language="zh-CN",
        timezone="Asia/Shanghai",
    )
