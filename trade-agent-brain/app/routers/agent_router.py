"""Agent API 路由"""
import asyncio
import json
from starlette.responses import StreamingResponse
from app.services.chat_storage_service import ChatStorageService
from app.services.chat_milvus_service import get_chat_milvus_service
from app.utils.snowflake import generate_id
from app.agents.orchestrator import create_cross_border_agent
from fastapi import APIRouter, HTTPException, status, Depends
from loguru import logger
from app.models.schemas import ApiResponse, AgentResponse, AgentRequest, ResumeRequest, UserContext
from app.services.auth_service import get_current_user

router = APIRouter()


@router.post("/chat", response_model=ApiResponse)
async def chat_with_agent(request: AgentRequest, current_user=Depends(get_current_user)):
    agent = await create_cross_border_agent(user_context=current_user, session_id=request.session_id)

    # 1. 持久化用户消息
    user_msg_id = f"human-{generate_id()}"
    asyncio.create_task(_persist_message(
        msg_id=user_msg_id,
        user_id=current_user.user_id,
        session_id=request.session_id or agent.session_id,
        role="human",
        content=request.message,
    ))

    # 2. 调用 Agent
    result = await agent.chat(message=request.message, thread_id=request.session_id)

    # 3. 持久化 AI 响应
    ai_content = result.get("message", "")
    if ai_content:
        ai_msg_id = f"ai-{generate_id()}"
        asyncio.create_task(_persist_message(
            msg_id=ai_msg_id,
            user_id=current_user.user_id,
            session_id=request.session_id or agent.session_id,
            role="ai",
            content=ai_content,
        ))

    return ApiResponse(code=200, message="success", data=ai_content)


@router.post("/chat_streaming")
async def chat_with_agent_streaming(request: AgentRequest, current_user=Depends(get_current_user)):
    async def event_generator():
        chunks: list[str] = []
        session_id = request.session_id

        try:
            agent = await create_cross_border_agent(
                user_context=current_user, session_id=session_id,
            )
            session_id = session_id or agent.session_id

            # 持久化用户消息（在流开始前）
            asyncio.create_task(_persist_message(
                msg_id=f"human-{generate_id()}",
                user_id=current_user.user_id,
                session_id=session_id,
                role="human",
                content=request.message,
            ))

            async for data in agent.chat_stream(
                    message=request.message, thread_id=session_id,
            ):
                # 解析 event 并累积 token
                try:
                    event_obj = json.loads(data)
                    if event_obj.get("event") == "token":
                        chunks.append(event_obj.get("content", ""))
                except json.JSONDecodeError:
                    pass

                yield f"data: {data}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'event': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

        finally:
            #无论正常结束、客户端断开、异常，都在此落盘
            full_response = "".join(chunks)
            if full_response.strip():
                asyncio.create_task(_persist_message(
                    msg_id=f"ai-{generate_id()}",
                    user_id=current_user.user_id,
                    session_id=session_id,
                    role="ai",
                    content=full_response,
                ))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
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



async def _persist_message(msg_id: str, user_id: int, session_id: str, role: str, content: str):
    """异步持久化到 MySQL + Milvus"""
    try:
        # 1. MySQL
        ChatStorageService.save_message(
            msg_id=msg_id, user_id=user_id,
            session_id=session_id, role=role, content=content,
        )
        # 2. Milvus 向量
        svc = get_chat_milvus_service()
        await svc.save_message_vector(
            context_text=content, msg_id=msg_id,
            user_id=user_id, session_id=session_id, role=role,
        )
    except Exception as e:
        logger.error(f"持久化失败 [{role}]: {e}")