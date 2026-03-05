# Desktop Open Agent

这是个demo！！！！，目的是体验deepagent的文件系统，功能已经走通了，就是没有加标准的skills，bug很多，只是个人小兴趣。

一个用自然语言操作桌面的小工具，说句话就能帮你打开应用、写文件、生成 Word 和 Excel。

技术栈是 LangGraph + 千问 + FastAPI，跑在本地，不依赖云端桌面控制。

## 为什么做这个

每次想打开个软件还得在开始菜单里翻半天，烦的不行。干脆写了个 Agent，跟它说"打开微信"就完事了。后来又加了文件生成的功能，可以直接让它帮你写代码、写文档丢桌面上，省的自已动手建文件。

## 怎么跑起来

装依赖：

```bash
pip install -r requirements.txt
```

复制一份配置文件：

```bash
cp .env.example .env
```

然后把你的百练 API Key 填进 `.env` 里：

```
DASHSCOPE_API_KEY=sk-你的key
```

启动：

```bash
python -m app.main
```

跑起来之后浏览器打开 http://127.0.0.1:8000/docs 就能看到接口文档。

## 能干嘛

### 1. 打开应用

跟它说就行，中英文都认，别名也支持。

```bash
curl -X POST http://127.0.0.1:8000/api/v1/desktop/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "帮我打开微信"}'
```

目前支持这些应用：

| 应用 | 怎么叫都行 |
|------|-----------|
| 微信 | 微信 / wechat / wx |
| QQ | qq / 腾讯QQ |
| 钉钉 | 钉钉 / dingtalk / dd |
| 飞书 | 飞书 / feishu / lark |
| Chrome | chrome / 谷歌浏览器 / 浏览器 |
| Edge | edge / 微软浏览器 |
|            |                              |
| 记事本 | notepad / 记事本 |
| 计算器 | calc / 计算器 |
| 文件管理器 | explorer / 我的电脑 |
| 终端 | terminal / cmd / 命令行 |
| Spotify | spotify / 音乐 |
| 网易云音乐 | 网易云 / 云音乐 |

找不到你的应用？去 `app/backends/local_shell_backend.py` 里的 `APP_REGISTRY` 加一条就行，格式照着抄。

### 2. 生成文件到桌面

这个是比较实用的功能。基本上你能想到的文件类型都能生成，没有做限制。

**文本类文件（代码、文档、配置什么的）：**

```
"帮我写一个 Python 爬虫脚本"  → 桌面上出现 爬虫脚本.py
"写个 Java Hello World"       → HelloWorld.java
"生成 nginx 配置文件"          → nginx.conf
"帮我写个 HTML 页面"           → index.html
"写个 SQL 建表语句"            → create_tables.sql
```

反正 .py .java .js .ts .go .c .cpp .sh .bat .md .txt .json .yaml .xml .csv .sql .html .css... 随便什么都行，只要是文本内容的文件都能写。

**Word 文档 (.docx)：**

```
"帮我写一份工作周报，Word 格式"  → 工作周报.docx
"写个项目方案文档"              → 项目方案.docx
```

内容用 Markdown 格式写，会自动转成 Word 的标题、列表、加粗这些，样式还过的去。

**Excel 表格 (.xlsx)：**

```
"做一个班级成绩单"    → 班级成绩单.xlsx
"帮我建个记账表"      → 记账表.xlsx
```

表格自带样式，表头有颜色，列宽自动适配，不用自已再调格式。

### 3. 查看桌面文件

```
"桌面上有哪些文件"  → 列出所有文件和文件夹
```

### 4. 流式响应

也支持 SSE 流式输出，写长文件的时候可以实时看到进度：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/desktop/chat_streaming \
  -H "Content-Type: application/json" \
  -d '{"message": "帮我写一篇小说放桌面"}'
```

## 大概的架构

```
用户说话  →  FastAPI 路由  →  LangGraph Agent (千问理解意图)
                                    ↓
                             选择合适的工具调用
                            /       |        \
                   打开应用    写文本文件    生成Word/Excel
                      ↓          ↓              ↓
               LocalShellBackend  写到桌面    python-docx / openpyxl
```

应用启动那块做了 5 级路径探测（预设路径 → 注册表 → where 命令 → 桌面快捷方式 → UWP 兜底），基本上只要你装了就能找到。

## 项目结构

```
desktop-open-agent/
├── app/
│   ├── main.py                      # 入口
│   ├── agents/
│   │   └── desktop_orchestrator.py  # Agent 编排，系统提示词在这
│   ├── backends/
│   │   └── local_shell_backend.py   # 应用启动的核心逻辑
│   ├── config/
│   │   ├── settings.py              # 配置
│   │   └── llm_config.py            # 模型配置
│   ├── models/
│   │   └── schemas.py               # 请求响应模型
│   ├── routers/
│   │   └── desktop_router.py        # API 路由
│   └── tools/
│       ├── app_launcher.py          # 打开应用的工具
│       └── file_operator.py         # 文件生成的工具 (文本/Word/Excel)
├── skills/
│   └── app-launcher/
│       └── SKILL.md
├── .env.example
├── requirements.txt
└── README.md
```

## 后续想做的

- [ ] 支持读取和编辑已有文件
- [ ] 加个 PPT 生成
- [ ] 接入更多模型（目前只接了千问）
- [ ] 做个简单的前端页面
- [ ] 支持语音输入

## 注意

- 目前主要在 Windows 上测试过，并且是demo，目的是体验deepagent的文件系统
- 生成 Word 和 Excel 需要额外装 `python-docx` 和 `openpyxl`，已经写在 requirements 里了
- 千问的 API Key 去阿里云百炼平台申请，有免费额度
