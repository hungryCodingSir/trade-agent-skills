# 🖥️ Desktop Open Agent

通过自然语言指令打开 Windows 桌面应用的智能助手。

基于 **LangGraph + 千问大模型 + LocalShellBackend** 构建。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

```bash
cp .env.example .env
```

编辑 `.env`，填入你的阿里百炼 API Key：

```
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx
```

### 3. 启动

```bash
python -m app.main
```

或者：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

启动后访问 Swagger 文档：http://127.0.0.1:8000/docs

## API 接口

### POST `/api/v1/desktop/chat` — 打开应用

```bash
curl -X POST http://127.0.0.1:8000/api/v1/desktop/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "帮我打开微信"}'
```

响应：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "reply": "已为您打开微信 ✅",
    "session_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  }
}
```

### POST `/api/v1/desktop/chat_streaming` — 打开应用（SSE 流式）

```bash
curl -X POST http://127.0.0.1:8000/api/v1/desktop/chat_streaming \
  -H "Content-Type: application/json" \
  -d '{"message": "帮我打开微信"}'
```

### GET `/api/v1/desktop/apps` — 列出可启动的应用

```bash
curl http://127.0.0.1:8000/api/v1/desktop/apps
```

## 支持的应用

| 应用 | 名称 / 别名 |
|------|-------------|
| 微信 | `微信` / `wechat` / `wx` |
| QQ | `QQ` / `qq` / `腾讯QQ` |
| 钉钉 | `钉钉` / `dingtalk` / `dd` |
| 飞书 | `飞书` / `feishu` / `lark` |
| Chrome | `chrome` / `谷歌浏览器` / `浏览器` |
| Edge | `edge` / `Edge浏览器` / `微软浏览器` |
| VS Code | `vscode` / `vs code` / `代码编辑器` |
| 记事本 | `记事本` / `notepad` |
| 计算器 | `计算器` / `calc` |
| 文件管理器 | `explorer` / `资源管理器` / `我的电脑` |
| 终端 | `终端` / `terminal` / `cmd` |
| Spotify | `spotify` / `音乐` |
| 网易云音乐 | `网易云` / `网易云音乐` |

## 添加新应用

编辑 `app/backends/local_shell_backend.py` 中的 `APP_REGISTRY`：

```python
APP_REGISTRY["your_app"] = AppProfile(
    name="your_app",
    display_name="你的应用",
    windows_paths=[r"C:\path\to\app.exe"],
    windows_exe="app.exe",
    aliases=["你的应用", "your_app", "别名"],
)
```

## 架构

```
POST /api/v1/desktop/chat  {"message": "帮我打开微信"}
         │
    desktop_router.py          (FastAPI 路由)
         │
    desktop_orchestrator.py    (LLM 理解意图 → 决定调用工具)
         │
    app_launcher.py            (open_application LangChain Tool)
         │
    LocalShellBackend          (5 级路径探测 → 启动应用)
         │
    Windows: start "" "...\WeChat.exe"  →  微信启动 ✅
```

## 项目结构

```
desktop-open-agent/
├── app/
│   ├── main.py                    # FastAPI 入口
│   ├── agents/
│   │   └── desktop_orchestrator.py  # Agent 编排器
│   ├── backends/
│   │   └── local_shell_backend.py   # Shell 执行后端
│   ├── config/
│   │   ├── settings.py              # 全局配置
│   │   └── llm_config.py            # LLM 配置
│   ├── models/
│   │   └── schemas.py               # 数据模型
│   ├── routers/
│   │   └── desktop_router.py        # API 路由
│   └── tools/
│       └── app_launcher.py          # 应用启动工具
├── skills/
│   └── app-launcher/
│       └── SKILL.md                 # 技能描述文件
├── .env.example
├── requirements.txt
└── README.md
```
