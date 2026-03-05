"""
桌面操作 Agent 编排器

使用 LocalShellBackend + LangGraph 构建的轻量桌面助手。
接收自然语言指令 → LLM 理解意图 → 调用工具打开应用。
"""
import json
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

from deepagents import create_deep_agent
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph
from loguru import logger

from app.backends.local_shell_backend import get_shell_backend
from app.config.llm_config import model
from app.tools import get_all_tools


# ────────────────────────────────────────────
# 系统提示词
# ────────────────────────────────────────────

SYSTEM_PROMPT = """你是一个 Windows 桌面智能助手，帮用户通过自然语言完成桌面操作。

══════════════════════════════════════
🎯 你的能力
══════════════════════════════════════

【能力一：打开应用】
调用 open_application 打开应用，调用 list_available_apps 列出可用应用。

【能力二：创建文件到桌面】
调用 create_file_on_desktop 在桌面上创建文件。
你可以根据用户需求自由创作内容（故事、笔记、备忘录、周报、代码等），
然后将内容保存为文件放到桌面上。文件名尽量中文、直观。

【能力三：查看桌面文件】
调用 list_desktop_files 列出桌面上的所有文件。

══════════════════════════════════════
💡 推理示例
══════════════════════════════════════
- "帮我打开微信" → open_application("微信")
- "打开浏览器" → open_application("chrome")
- "写个睡前故事放桌面上" → 创作故事内容 → create_file_on_desktop("睡前故事.md", 故事内容)
- "帮我写个今日待办" → 生成待办清单 → create_file_on_desktop("今日待办.md", 待办内容)
- "桌面上有哪些文件" → list_desktop_files()
- "帮我写一首诗保存下来" → 创作诗歌 → create_file_on_desktop("诗歌.md", 诗歌内容)

══════════════════════════════════════
✍️ 创作要求
══════════════════════════════════════
当用户要求创作内容（故事/文章/笔记等）时：
- 内容要丰富、有质量，不要敷衍
- 故事至少 500 字，有角色、情节、结局
- 使用 Markdown 格式排版，标题用 #，适当分段
- 文件名用中文，简洁明了

══════════════════════════════════════
⚠️ 注意事项
══════════════════════════════════════
- 用简洁中文回复
- 操作成功后简短确认，告知文件名即可
- 操作失败时告知原因
- 超出能力范围的请求礼貌拒绝
"""


# ────────────────────────────────────────────
# Agent 单例
# ────────────────────────────────────────────

_agent: Optional[CompiledStateGraph] = None
_id_counter = 0


def _next_id() -> str:
    global _id_counter
    _id_counter += 1
    return str(_id_counter)


def init_agent() -> None:
    """初始化桌面 Agent（进程级单例）。"""
    global _agent

    tools = get_all_tools()
    shell_backend = get_shell_backend()

    _agent = create_deep_agent(
        model=model,
        tools=tools,
        subagents=[],
        system_prompt=SYSTEM_PROMPT,
        checkpointer=MemorySaver(),
    )

    logger.info(
        f"Desktop Agent initialized | "
        f"tools={[t.name for t in tools]} | "
        f"apps={len(shell_backend.app_registry)}"
    )


def get_agent() -> CompiledStateGraph:
    """获取 Agent 实例，支持延迟初始化。"""
    if _agent is None:
        init_agent()
    return _agent


# ────────────────────────────────────────────
# 对话服务
# ────────────────────────────────────────────

async def chat(message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    非流式对话。

    Args:
        message: 用户指令，如 "帮我打开微信"
        session_id: 会话ID（可选）

    Returns:
        {"message": "已为您打开微信 ✅", "session_id": "xxx"}
    """
    agent = get_agent()
    session_id = session_id or str(uuid.uuid4())

    config: RunnableConfig = {"configurable": {"thread_id": session_id}}
    input_data = {
        "messages": [HumanMessage(content=message, id=f"human-{_next_id()}")],
    }

    try:
        result = await agent.ainvoke(input=input_data, config=config)
        messages = result.get("messages", [])
        last_message = messages[-1] if messages else None

        return {
            "message": last_message.content if last_message else "无响应",
            "session_id": session_id,
        }
    except Exception as e:
        logger.error(f"Desktop Agent error: {e}", exc_info=True)
        raise


async def chat_stream(
    message: str,
    session_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    SSE 流式对话。

    Yields SSE JSON 字符串：
      - token      : LLM 文本片段
      - tool_start : 工具调用开始
      - tool_end   : 工具调用结束
      - done       : 流结束
      - error      : 异常
    """
    agent = get_agent()
    session_id = session_id or str(uuid.uuid4())

    config: RunnableConfig = {"configurable": {"thread_id": session_id}}
    input_data = {
        "messages": [HumanMessage(content=message, id=f"human-{_next_id()}")],
    }

    full_content = ""

    try:
        async for event in agent.astream_events(
            input=input_data, config=config, version="v2",
        ):
            kind = event.get("event", "")

            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    token_text = chunk.content
                    full_content += token_text
                    yield json.dumps({
                        "event": "token",
                        "content": token_text,
                    }, ensure_ascii=False)

            elif kind == "on_tool_start":
                yield json.dumps({
                    "event": "tool_start",
                    "tool": event.get("name", "unknown"),
                    "input": event.get("data", {}).get("input", {}),
                }, ensure_ascii=False)

            elif kind == "on_tool_end":
                output = str(event.get("data", {}).get("output", ""))
                if len(output) > 500:
                    output = output[:500] + "..."
                yield json.dumps({
                    "event": "tool_end",
                    "tool": event.get("name", "unknown"),
                    "output": output,
                }, ensure_ascii=False)

        yield json.dumps({
            "event": "done",
            "content": full_content,
            "session_id": session_id,
        }, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Desktop Agent stream error: {e}", exc_info=True)
        yield json.dumps({
            "event": "error",
            "content": f"流式响应异常: {str(e)}",
        }, ensure_ascii=False)
