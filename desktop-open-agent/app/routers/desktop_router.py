"""
桌面操作 API 路由

接口：
  POST /chat             自然语言打开应用（非流式）
  POST /chat_streaming   自然语言打开应用（SSE 流式）
  GET  /apps             列出所有可启动的应用
"""
import json
import uuid

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from starlette.responses import StreamingResponse

from app.agents import desktop_orchestrator
from app.backends.local_shell_backend import get_shell_backend
from app.models.schemas import ApiResponse, DesktopRequest

router = APIRouter()


@router.post("/chat", response_model=ApiResponse, summary="桌面助手对话")
async def desktop_chat(request: DesktopRequest):
    """
    自然语言桌面操作（非流式）。

    请求示例:
    ```json
    {"message": "帮我打开微信"}
    {"message": "打开浏览器"}
    {"message": "我要写代码"}
    {"message": "你能打开什么应用？"}
    ```
    """
    session_id = request.session_id or str(uuid.uuid4())

    try:
        result = await desktop_orchestrator.chat(
            message=request.message,
            session_id=session_id,
        )
        return ApiResponse(
            code=200, message="success",
            data={
                "reply": result.get("message", ""),
                "session_id": result.get("session_id", session_id),
            },
        )
    except Exception as e:
        logger.error(f"Desktop chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"桌面操作失败: {str(e)}",
        )


@router.post("/chat_streaming", summary="桌面助手对话（SSE 流式）")
async def desktop_chat_streaming(request: DesktopRequest):
    """
    自然语言桌面操作（SSE 流式）。

    返回 Server-Sent Events 流，事件类型：
    token / tool_start / tool_end / done / error
    """
    session_id = request.session_id or str(uuid.uuid4())

    async def event_generator():
        try:
            async for data in desktop_orchestrator.chat_stream(
                message=request.message,
                session_id=session_id,
            ):
                yield f"data: {data}\n\n"
        except Exception as e:
            logger.error(f"Desktop streaming error: {e}")
            yield f"data: {json.dumps({'event': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/apps", response_model=ApiResponse, summary="列出可启动的应用")
async def list_apps():
    """列出当前系统上所有已注册的可启动应用。"""
    backend = get_shell_backend()
    apps = backend.list_applications()
    return ApiResponse(code=200, message="success", data=apps)
