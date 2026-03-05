"""
桌面文件操作工具

在用户桌面上创建文件、读取文件、列出文件等。
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List

from langchain_core.tools import BaseTool, tool
from loguru import logger


def _get_desktop_path() -> str:
    """获取当前用户的桌面路径（兼容中英文系统）。"""
    # Windows 标准方式
    if os.name == "nt":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            )
            desktop, _ = winreg.QueryValueEx(key, "Desktop")
            winreg.CloseKey(key)
            return desktop
        except Exception:
            pass

    # 通用回退
    home = str(Path.home())
    for name in ["Desktop", "桌面"]:
        path = os.path.join(home, name)
        if os.path.isdir(path):
            return path

    return os.path.join(home, "Desktop")


@tool
async def create_file_on_desktop(filename: str, content: str) -> str:
    """在用户的电脑桌面上创建一个文件并写入内容。

    适用场景：
    - 用户要求写一篇文章/故事/笔记并保存到桌面
    - 用户要求创建备忘录、待办清单、学习笔记等
    - 用户要求生成任何文本文件到桌面

    文件会直接出现在用户的桌面上。

    Args:
        filename: 文件名（含扩展名），如 "睡前故事.md"、"备忘录.txt"、"周报.md"
        content: 文件内容（支持 Markdown 格式）
    """
    try:
        desktop = _get_desktop_path()
        filepath = os.path.join(desktop, filename)

        # 如果文件已存在，自动加时间戳避免覆盖
        if os.path.exists(filepath):
            name, ext = os.path.splitext(filename)
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"{name}_{timestamp}{ext}"
            filepath = os.path.join(desktop, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        file_size = os.path.getsize(filepath)
        line_count = content.count("\n") + 1

        logger.info(f"文件已创建: {filepath} ({file_size} bytes, {line_count} lines)")

        return json.dumps({
            "success": True,
            "message": f"文件已保存到桌面: {filename}",
            "filepath": filepath,
            "filename": filename,
            "size_bytes": file_size,
            "line_count": line_count,
        }, ensure_ascii=False)

    except PermissionError:
        return json.dumps({
            "success": False,
            "message": f"没有写入权限，无法在桌面创建文件: {filename}",
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"创建文件失败: {e}")
        return json.dumps({
            "success": False,
            "message": f"创建文件失败: {type(e).__name__}: {e}",
        }, ensure_ascii=False)


@tool
async def list_desktop_files() -> str:
    """列出用户桌面上的所有文件和文件夹。

    当用户想知道桌面上有什么文件时调用此工具。
    """
    try:
        desktop = _get_desktop_path()
        items = []
        for name in sorted(os.listdir(desktop)):
            full_path = os.path.join(desktop, name)
            if os.path.isdir(full_path):
                items.append({"name": name, "type": "folder"})
            else:
                size = os.path.getsize(full_path)
                _, ext = os.path.splitext(name)
                items.append({
                    "name": name,
                    "type": "file",
                    "extension": ext,
                    "size_kb": round(size / 1024, 1),
                })

        return json.dumps({
            "success": True,
            "desktop_path": desktop,
            "total_items": len(items),
            "items": items,
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"读取桌面失败: {e}",
        }, ensure_ascii=False)


FILE_TOOLS: List[BaseTool] = [create_file_on_desktop, list_desktop_files]


def get_file_tools() -> List[BaseTool]:
    return list(FILE_TOOLS)
