"""Agent API 路由"""
from fastapi import APIRouter, HTTPException, status, Depends
from loguru import logger

from app.agents.orchestrator import create_cross_border_agent
from app.models.schemas import ApiResponse, AgentResponse, AgentRequest, ResumeRequest, UserContext
from app.services.auth_service import get_current_user

router = APIRouter()


@router.post("/chat", response_model=ApiResponse)
async def chat_with_agent(
    request: AgentRequest,
    current_user: UserContext = Depends(get_current_user),
):
    """与 Agent 对话（非流式）"""
    try:
        agent = await create_cross_border_agent(
            user_context=current_user,
            session_id=request.session_id,
        )

        result = await agent.chat(message=request.message, thread_id=request.session_id)

        response = AgentResponse(
            message=result.get("message", ""),
            session_id=result.get("session_id", ""),
            tool_calls=result.get("tool_calls"),
            metadata={
                "requires_approval": result.get("requires_approval", False),
                "pending_action": result.get("pending_action"),
            } if result.get("requires_approval") else None,
        )

        return ApiResponse(code=200, message="success", data=response)

    except Exception as e:
        logger.error(f"Agent chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"智能体响应失败: {str(e)}",
        )


@router.post("/chat_streaming")
async def chat_with_agent_streaming(
    request: AgentRequest,
    current_user: UserContext = Depends(get_current_user),
):
    """与 Agent 对话（SSE 流式输出）"""
    import json
    from starlette.responses import StreamingResponse

    async def event_generator():
        try:
            agent = await create_cross_border_agent(
                user_context=current_user,
                session_id=request.session_id,
            )

            async for data in agent.chat_stream(
                message=request.message,
                thread_id=request.session_id,
            ):
                # SSE 格式: "data: ...\n\n"
                yield f"data: {data}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'event': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),media_type="text/event-stream",
        headers={"Cache-Control": "no-cache","Connection": "keep-alive","X-Accel-Buffering": "no"},
    )

@router.post("/resume", response_model=ApiResponse)
async def resume_interrupted_agent(
    request: ResumeRequest,
    current_user: UserContext = Depends(get_current_user),
):
    """恢复被中断的 Agent（邮件发送确认场景）"""
    try:
        agent = await create_cross_border_agent(
            user_context=current_user,
            session_id=request.session_id,
        )

        decision = {"decision": request.decision}
        if request.reason:
            decision["reason"] = request.reason
        if request.edited_subject:
            decision["edited_subject"] = request.edited_subject
        if request.edited_content:
            decision["edited_content"] = request.edited_content
        if request.edited_to_email:
            decision["edited_to_email"] = request.edited_to_email

        result = await agent.resume(
            decision=decision,
            thread_id=request.session_id,
        )

        response = AgentResponse(
            message=result.get("message", ""),
            session_id=result.get("session_id", ""),
            metadata={
                "resumed": True,
                "decision": result.get("decision"),
            },
        )

        return ApiResponse(code=200, message="success", data=response)

    except Exception as e:
        logger.error(f"Agent resume error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"恢复执行失败: {str(e)}",
        )


@router.get("/health")
async def health_check():
    return {"status": "ok", "version": "2.0.0"}