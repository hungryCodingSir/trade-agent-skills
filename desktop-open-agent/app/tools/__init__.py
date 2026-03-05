from app.tools.app_launcher import get_desktop_tools, open_application, list_available_apps
from app.tools.file_operator import get_file_tools, create_file_on_desktop, list_desktop_files


def get_all_tools():
    """返回所有桌面助手工具。"""
    return get_desktop_tools() + get_file_tools()


__all__ = [
    "get_all_tools",
    "get_desktop_tools",
    "get_file_tools",
    "open_application",
    "list_available_apps",
    "create_file_on_desktop",
    "list_desktop_files",
]
