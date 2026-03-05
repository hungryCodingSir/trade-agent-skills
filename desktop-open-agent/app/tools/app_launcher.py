"""
应用启动工具 — 将 LocalShellBackend 封装为 LangChain Tool
"""
import json
from typing import List

from langchain_core.tools import BaseTool, tool
from loguru import logger

from app.backends.local_shell_backend import get_shell_backend


@tool
async def open_application(app_name: str) -> str:
    """打开用户电脑上已安装的应用程序。

    支持中英文名称和常见别名，例如：
    - "微信" / "wechat" / "wx"
    - "钉钉" / "dingtalk" / "dd"
    - "谷歌浏览器" / "chrome"
    - "飞书" / "feishu" / "lark"
    - "记事本" / "notepad"
    - "计算器" / "calculator"
    - "文件管理器" / "explorer"
    - "vscode" / "vs code"
    - "QQ" / "qq"
    - "网易云音乐" / "网易云"
    - "终端" / "terminal" / "cmd"

    Args:
        app_name: 要打开的应用名称（中英文均可）
    """
    backend = get_shell_backend()
    result = await backend.open_application(app_name)
    logger.info(f"open_application({app_name}) → {result.success}: {result.message}")
    return json.dumps(result.to_dict(), ensure_ascii=False)


@tool
async def list_available_apps() -> str:
    """列出当前系统上所有可以打开的应用程序。

    返回每个应用的名称、显示名和可用别名。
    当用户询问"你能打开哪些应用"或不确定应用名称时调用此工具。
    """
    backend = get_shell_backend()
    apps = backend.list_applications()
    return json.dumps(apps, ensure_ascii=False, indent=2)


DESKTOP_TOOLS: List[BaseTool] = [open_application, list_available_apps]


def get_desktop_tools() -> List[BaseTool]:
    return list(DESKTOP_TOOLS)
