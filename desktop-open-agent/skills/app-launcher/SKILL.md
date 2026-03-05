---
name: app-launcher
description: 当用户要求打开、启动、运行电脑上的应用程序时使用此技能。支持中英文应用名称和常见别名。
version: 1.0.0
tags: [应用, 打开, 启动, 桌面, app, launch, open, desktop]
---

# 应用启动技能

## 概述

通过自然语言指令打开 Windows / macOS / Linux 上已安装的应用程序。
底层使用 `LocalShellBackend` 自动探测应用安装路径并启动。

## 可用工具

| 工具 | 说明 |
|------|------|
| `open_application(app_name)` | 打开指定应用，支持中英文别名 |
| `list_available_apps()` | 列出所有可打开的应用清单 |

## 已注册应用

| 应用 | 名称 / 别名 |
|------|-------------|
| 微信 | wechat, wx, 微信, weixin |
| QQ | qq, 腾讯QQ |
| 钉钉 | dingtalk, dd, 钉钉 |
| 飞书 | feishu, lark, 飞书 |
| Chrome | chrome, 谷歌浏览器, 浏览器 |
| Edge | edge, Edge浏览器, 微软浏览器 |
| VS Code | vscode, vs code, 代码编辑器 |
| 记事本 | notepad, 记事本 |
| 计算器 | calculator, calc, 计算器 |
| 文件管理器 | explorer, 资源管理器, 我的电脑 |
| 终端 | terminal, cmd, 命令行, powershell |
| Spotify | spotify, 音乐 |
| 网易云音乐 | 网易云, 云音乐 |

## Windows 路径探测策略（按优先级）

1. **预设路径** — 直接检查常见安装位置
2. **注册表** — 查询 `HKLM/HKCU\App Paths`
3. **PATH 搜索** — `where xxx.exe`
4. **桌面快捷方式** — glob 搜索 `*.lnk`
5. **UWP 兜底** — `start` 命令启动

## 扩展新应用

在 `app/backends/local_shell_backend.py` 的 `APP_REGISTRY` 中添加即可。
