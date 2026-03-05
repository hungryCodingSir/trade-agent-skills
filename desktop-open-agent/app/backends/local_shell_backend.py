"""
本地 Shell 执行后端

在本地机器上安全执行 Shell 命令，支持：
- 应用启动（白名单 + 自动探测安装路径）
- 跨平台兼容（Windows / macOS / Linux）
- 安全沙箱（命令白名单 + 危险命令拦截 + 执行超时）

用法：
    backend = LocalShellBackend()
    result = await backend.open_application("微信")
"""
import asyncio
import glob
import os
import platform
import re
import subprocess
from dataclasses import dataclass, field

try:
    import winreg
except ImportError:
    winreg = None  # type: ignore[assignment]

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from loguru import logger


# ────────────────────────────────────────────
# 数据模型
# ────────────────────────────────────────────

class OSType(str, Enum):
    WINDOWS = "windows"
    MACOS = "darwin"
    LINUX = "linux"


@dataclass
class AppProfile:
    """应用程序配置档案"""
    name: str                             # 应用标识（英文小写）
    display_name: str                     # 显示名称
    windows_paths: List[str] = field(default_factory=list)
    windows_exe: str = ""
    macos_bundle: str = ""
    linux_commands: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)


@dataclass
class ShellResult:
    """命令执行结果"""
    success: bool
    message: str
    return_code: int = 0
    stdout: str = ""
    stderr: str = ""
    app_name: str = ""
    app_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "success": self.success,
            "message": self.message,
        }
        if self.app_name:
            d["app_name"] = self.app_name
        if self.app_path:
            d["app_path"] = self.app_path
        if not self.success:
            d["return_code"] = self.return_code
            if self.stderr:
                d["stderr"] = self.stderr[:500]
        return d


# ────────────────────────────────────────────
# 应用注册表（白名单）
# ────────────────────────────────────────────

_HOME = str(Path.home())

APP_REGISTRY: Dict[str, AppProfile] = {
    "wechat": AppProfile(
        name="wechat",
        display_name="微信",
        windows_paths=[
            os.path.join(_HOME, "AppData", "Local", "WeChat", "WeChat.exe"),
            os.path.join(_HOME, "AppData", "Roaming", "Tencent", "WeChat", "WeChat.exe"),
            r"C:\Program Files (x86)\Tencent\WeChat\WeChat.exe",
            r"C:\Program Files\Tencent\WeChat\WeChat.exe",
            r"D:\Program Files (x86)\Tencent\WeChat\WeChat.exe",
            r"D:\Program Files\Tencent\WeChat\WeChat.exe",
            r"D:\Software\WeChat\WeChat.exe",
            os.path.join(_HOME, "Desktop", "微信.lnk"),
            os.path.join(_HOME, "桌面", "微信.lnk"),
            os.path.join(_HOME, "Desktop", "WeChat.lnk"),
        ],
        windows_exe="WeChat.exe",
        macos_bundle="com.tencent.xinWeChat",
        linux_commands=["wechat", "wechat-universal", "com.tencent.WeChat"],
        aliases=["微信", "wx", "weixin"],
    ),
    "qq": AppProfile(
        name="qq",
        display_name="QQ",
        windows_paths=[
            os.path.join(_HOME, "AppData", "Local", "QQ", "QQ.exe"),
            r"C:\Program Files (x86)\Tencent\QQ\Bin\QQ.exe",
            r"C:\Program Files\Tencent\QQ\Bin\QQ.exe",
            r"D:\Program Files (x86)\Tencent\QQ\Bin\QQ.exe",
            os.path.join(_HOME, "Desktop", "QQ.lnk"),
            os.path.join(_HOME, "桌面", "QQ.lnk"),
        ],
        windows_exe="QQ.exe",
        macos_bundle="com.tencent.qq",
        linux_commands=["qq", "linuxqq"],
        aliases=["qq", "腾讯QQ"],
    ),
    "dingtalk": AppProfile(
        name="dingtalk",
        display_name="钉钉",
        windows_paths=[
            os.path.join(_HOME, "AppData", "Local", "DingTalk", "DingtalkLauncher.exe"),
            r"C:\Program Files (x86)\DingTalk\DingtalkLauncher.exe",
            r"C:\Program Files\DingTalk\DingtalkLauncher.exe",
        ],
        windows_exe="DingtalkLauncher.exe",
        macos_bundle="com.alibaba.DingTalkMac",
        linux_commands=["dingtalk"],
        aliases=["钉钉", "dd"],
    ),
    "feishu": AppProfile(
        name="feishu",
        display_name="飞书",
        windows_paths=[
            os.path.join(_HOME, "AppData", "Local", "Feishu", "Feishu.exe"),
            r"C:\Program Files\Feishu\Feishu.exe",
        ],
        windows_exe="Feishu.exe",
        macos_bundle="com.bytedance.lark",
        linux_commands=["feishu", "bytedance-feishu"],
        aliases=["飞书", "lark"],
    ),
    "chrome": AppProfile(
        name="chrome",
        display_name="Google Chrome",
        windows_paths=[
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.join(_HOME, "AppData", "Local", "Google", "Chrome", "Application", "chrome.exe"),
        ],
        windows_exe="chrome.exe",
        macos_bundle="com.google.Chrome",
        linux_commands=["google-chrome", "google-chrome-stable", "chromium-browser"],
        aliases=["谷歌浏览器", "谷歌", "浏览器"],
    ),
    "edge": AppProfile(
        name="edge",
        display_name="Microsoft Edge",
        windows_paths=[
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        windows_exe="msedge.exe",
        macos_bundle="com.microsoft.edgemac",
        linux_commands=["microsoft-edge", "microsoft-edge-stable"],
        aliases=["edge", "Edge浏览器", "微软浏览器"],
    ),
    "vscode": AppProfile(
        name="vscode",
        display_name="Visual Studio Code",
        windows_paths=[
            os.path.join(_HOME, "AppData", "Local", "Programs", "Microsoft VS Code", "Code.exe"),
            r"C:\Program Files\Microsoft VS Code\Code.exe",
        ],
        windows_exe="Code.exe",
        macos_bundle="com.microsoft.VSCode",
        linux_commands=["code"],
        aliases=["vscode", "vs code", "代码编辑器"],
    ),
    "notepad": AppProfile(
        name="notepad",
        display_name="记事本",
        windows_paths=[r"C:\Windows\System32\notepad.exe"],
        windows_exe="notepad.exe",
        macos_bundle="",
        linux_commands=["gedit", "kate", "xed"],
        aliases=["记事本", "notepad"],
    ),
    "calculator": AppProfile(
        name="calculator",
        display_name="计算器",
        windows_paths=[r"C:\Windows\System32\calc.exe"],
        windows_exe="calc.exe",
        macos_bundle="com.apple.calculator",
        linux_commands=["gnome-calculator", "kcalc"],
        aliases=["计算器", "calc"],
    ),
    "explorer": AppProfile(
        name="explorer",
        display_name="文件资源管理器",
        windows_paths=[r"C:\Windows\explorer.exe"],
        windows_exe="explorer.exe",
        macos_bundle="com.apple.finder",
        linux_commands=["nautilus", "dolphin", "thunar", "nemo"],
        aliases=["文件管理器", "资源管理器", "我的电脑", "finder"],
    ),
    "terminal": AppProfile(
        name="terminal",
        display_name="终端",
        windows_paths=[
            os.path.join(_HOME, "AppData", "Local", "Microsoft", "WindowsApps", "wt.exe"),
            r"C:\Windows\System32\cmd.exe",
        ],
        windows_exe="wt.exe",
        macos_bundle="com.apple.Terminal",
        linux_commands=["gnome-terminal", "konsole", "xterm"],
        aliases=["终端", "命令行", "cmd", "terminal", "powershell"],
    ),
    "spotify": AppProfile(
        name="spotify",
        display_name="Spotify",
        windows_paths=[
            os.path.join(_HOME, "AppData", "Roaming", "Spotify", "Spotify.exe"),
        ],
        windows_exe="Spotify.exe",
        macos_bundle="com.spotify.client",
        linux_commands=["spotify"],
        aliases=["spotify", "音乐"],
    ),
    "netease_music": AppProfile(
        name="netease_music",
        display_name="网易云音乐",
        windows_paths=[
            os.path.join(_HOME, "AppData", "Local", "NetEase", "CloudMusic", "cloudmusic.exe"),
            r"C:\Program Files (x86)\NetEase\CloudMusic\cloudmusic.exe",
            r"D:\Program Files\NetEase\CloudMusic\cloudmusic.exe",
            os.path.join(_HOME, "Desktop", "网易云音乐.lnk"),
            os.path.join(_HOME, "桌面", "网易云音乐.lnk"),
        ],
        windows_exe="cloudmusic.exe",
        macos_bundle="",
        linux_commands=["netease-cloud-music"],
        aliases=["网易云音乐", "网易云", "云音乐"],
    ),
}


# ────────────────────────────────────────────
# 危险命令黑名单
# ────────────────────────────────────────────

DANGEROUS_PATTERNS = [
    r"\brm\s+(-rf?|--recursive)", r"\bformat\b", r"\bfdisk\b",
    r"\bmkfs\b", r"\bdd\s+if=", r"\b(shutdown|reboot|halt|poweroff)\b",
    r"\breg\s+(delete|add)\b", r"\bnet\s+(user|stop)\b",
    r"\bdel\s+/[sfq]", r"\brmdir\s+/s",
    r"\btaskkill\s+/f",
    r">\s*/dev/(sd|null|zero)", r"\bchmod\s+777\s+/",
]
_DANGEROUS_RE = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS]


def _is_dangerous(command: str) -> bool:
    return any(p.search(command) for p in _DANGEROUS_RE)


# ────────────────────────────────────────────
# LocalShellBackend 核心
# ────────────────────────────────────────────

class LocalShellBackend:
    """
    本地 Shell 执行后端

    职责：
    1. 应用启动 — 根据应用名自动探测路径并启动
    2. 安全命令执行 — 白名单 + 黑名单双重过滤
    3. 跨平台 — 自动适配 Windows / macOS / Linux

    安全模型：
    - open_application: 只能启动 APP_REGISTRY 中注册的应用（白名单）
    - execute: 可执行任意命令但会拦截危险命令（黑名单）
    - 所有执行均有超时控制
    """

    def __init__(
        self,
        timeout: int = 30,
        enable_raw_execute: bool = False,
        extra_apps: Optional[Dict[str, AppProfile]] = None,
    ):
        self.timeout = timeout
        self.enable_raw_execute = enable_raw_execute
        self.os_type = self._detect_os()
        self.app_registry: Dict[str, AppProfile] = {**APP_REGISTRY}
        if extra_apps:
            self.app_registry.update(extra_apps)

        # 构建别名索引
        self._alias_index: Dict[str, str] = {}
        for app_name, profile in self.app_registry.items():
            self._alias_index[app_name] = app_name
            self._alias_index[profile.display_name.lower()] = app_name
            for alias in profile.aliases:
                self._alias_index[alias.lower()] = app_name

        logger.info(
            f"LocalShellBackend initialized | os={self.os_type.value} | "
            f"registered_apps={len(self.app_registry)} | "
            f"raw_execute={'enabled' if enable_raw_execute else 'disabled'}"
        )

    # ── 公开方法 ──

    async def open_application(self, app_name: str) -> ShellResult:
        """打开指定应用程序，支持中英文名称和别名。"""
        normalized = app_name.strip().lower()
        resolved_name = self._alias_index.get(normalized)

        if not resolved_name:
            available = self.list_applications()
            return ShellResult(
                success=False,
                message=(
                    f"未识别的应用: '{app_name}'。\n"
                    f"当前支持的应用: {', '.join(a['display_name'] for a in available)}"
                ),
                app_name=app_name,
            )

        profile = self.app_registry[resolved_name]
        logger.info(f"正在启动应用: {profile.display_name} ({resolved_name})")

        if self.os_type == OSType.WINDOWS:
            return await self._open_windows(profile)
        elif self.os_type == OSType.MACOS:
            return await self._open_macos(profile)
        else:
            return await self._open_linux(profile)

    async def execute(self, command: str) -> ShellResult:
        """执行任意 Shell 命令（需启用 enable_raw_execute）。"""
        if not self.enable_raw_execute:
            return ShellResult(
                success=False,
                message="原始命令执行已禁用。请使用 open_application 打开应用。",
            )
        if _is_dangerous(command):
            logger.warning(f"[安全拦截] 危险命令被阻止: {command}")
            return ShellResult(
                success=False,
                message="安全限制：检测到危险命令，已阻止执行。",
            )
        return await self._run_command(command, shell=True)

    def list_applications(self) -> List[Dict[str, str]]:
        """列出所有已注册的可启动应用。"""
        return [
            {
                "name": profile.name,
                "display_name": profile.display_name,
                "aliases": ", ".join(profile.aliases),
            }
            for profile in self.app_registry.values()
        ]

    def resolve_app_name(self, user_input: str) -> Optional[str]:
        """将用户输入解析为标准应用名。"""
        return self._alias_index.get(user_input.strip().lower())

    # ── Windows ──

    async def _open_windows(self, profile: AppProfile) -> ShellResult:
        """
        Windows 启动策略（按优先级）：
        1. 预设路径列表直接匹配
        2. 注册表查询 App Paths
        3. where 命令搜索 PATH
        4. 桌面快捷方式 glob 搜索
        5. shell:AppsFolder（UWP 兜底）
        """
        # 策略 1：预设路径
        for path in profile.windows_paths:
            expanded = os.path.expandvars(path)
            if os.path.isfile(expanded):
                logger.info(f"[路径匹配] {expanded}")
                return await self._launch_windows(expanded, profile)

        # 策略 2：注册表
        reg_path = self._query_registry_app_path(profile.windows_exe)
        if reg_path and os.path.isfile(reg_path):
            logger.info(f"[注册表] {reg_path}")
            return await self._launch_windows(reg_path, profile)

        # 策略 3：where
        where_result = await self._run_command(f"where {profile.windows_exe}", shell=True)
        if where_result.success and where_result.stdout.strip():
            exe_path = where_result.stdout.strip().splitlines()[0]
            logger.info(f"[where] {exe_path}")
            return await self._launch_windows(exe_path, profile)

        # 策略 4：桌面快捷方式
        desktop_dirs = [
            os.path.join(_HOME, "Desktop"),
            os.path.join(_HOME, "桌面"),
            os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "Desktop"),
        ]
        for desktop in desktop_dirs:
            for ext in ("*.lnk", "*.url"):
                for shortcut in glob.glob(os.path.join(desktop, ext)):
                    shortcut_lower = os.path.basename(shortcut).lower()
                    match_names = [profile.display_name.lower(), profile.name.lower()]
                    match_names.extend(a.lower() for a in profile.aliases)
                    if any(name in shortcut_lower for name in match_names):
                        logger.info(f"[快捷方式] {shortcut}")
                        return await self._launch_windows(shortcut, profile)

        # 策略 5：UWP 兜底
        logger.info(f"[UWP 兜底] start {profile.windows_exe}")
        return await self._run_command(
            f'start "" "{profile.windows_exe}"',
            shell=True, app_name=profile.display_name,
        )

    @staticmethod
    def _query_registry_app_path(exe_name: str) -> Optional[str]:
        if winreg is None:
            return None
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                key = winreg.OpenKey(
                    hive,
                    rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}",
                )
                value, _ = winreg.QueryValueEx(key, None)
                winreg.CloseKey(key)
                return value
            except (FileNotFoundError, OSError):
                continue
        return None

    async def _launch_windows(self, path: str, profile: AppProfile) -> ShellResult:
        return await self._run_command(
            f'start "" "{path}"', shell=True,
            app_name=profile.display_name, app_path=path,
        )

    # ── macOS ──

    async def _open_macos(self, profile: AppProfile) -> ShellResult:
        if profile.macos_bundle:
            result = await self._run_command(
                f"open -b {profile.macos_bundle}",
                shell=True, app_name=profile.display_name,
            )
            if result.success:
                return result

        for d in ["/Applications", os.path.expanduser("~/Applications")]:
            for name_guess in [profile.display_name, profile.name.title(), profile.name]:
                app_path = os.path.join(d, f"{name_guess}.app")
                if os.path.isdir(app_path):
                    return await self._run_command(
                        f'open "{app_path}"', shell=True,
                        app_name=profile.display_name, app_path=app_path,
                    )

        return ShellResult(
            success=False,
            message=f"在 macOS 上未找到 {profile.display_name}，请确认已安装。",
            app_name=profile.display_name,
        )

    # ── Linux ──

    async def _open_linux(self, profile: AppProfile) -> ShellResult:
        for cmd in profile.linux_commands:
            which_result = await self._run_command(f"which {cmd}", shell=True)
            if which_result.success:
                return await self._run_command(
                    f"nohup {cmd} >/dev/null 2>&1 &", shell=True,
                    app_name=profile.display_name, app_path=cmd,
                )

        if profile.linux_commands:
            flatpak_result = await self._run_command(
                f"flatpak run {profile.linux_commands[0]}",
                shell=True, app_name=profile.display_name,
            )
            if flatpak_result.success:
                return flatpak_result

        return ShellResult(
            success=False,
            message=f"在 Linux 上未找到 {profile.display_name}，请确认已安装。",
            app_name=profile.display_name,
        )

    # ── 通用命令执行 ──
    #
    # 使用 subprocess.Popen + asyncio.to_thread 替代 asyncio.create_subprocess_shell
    # 原因：Windows 上 asyncio.create_subprocess_shell 需要 ProactorEventLoop，
    # 但 uvicorn 默认使用 SelectorEventLoop，会抛 NotImplementedError。
    # subprocess.Popen 在所有平台和事件循环下都能正常工作。

    def _run_command_sync(
        self, command: str, shell: bool = False,
        app_name: str = "", app_path: str = "",
    ) -> ShellResult:
        """同步执行命令（在线程池中被调用）。"""
        try:
            logger.debug(f"[exec] {command}")
            process = subprocess.Popen(
                command if shell else command.split(),
                shell=shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            try:
                stdout, stderr = process.communicate(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                return ShellResult(
                    success=False,
                    message=f"命令执行超时 ({self.timeout}s)",
                    return_code=-1, app_name=app_name,
                )

            return_code = process.returncode or 0
            stdout_str = stdout.decode("utf-8", errors="replace").strip() if stdout else ""
            stderr_str = stderr.decode("utf-8", errors="replace").strip() if stderr else ""

            success = return_code == 0 or (
                "start" in command.lower() and return_code <= 1
            )

            return ShellResult(
                success=success,
                message=f"已启动 {app_name}" if (success and app_name) else (
                    f"命令执行{'成功' if success else '失败'}"
                ),
                return_code=return_code,
                stdout=stdout_str, stderr=stderr_str,
                app_name=app_name, app_path=app_path,
            )

        except FileNotFoundError as e:
            return ShellResult(success=False, message=f"命令或路径不存在: {e}", app_name=app_name)
        except Exception as e:
            logger.error(f"命令执行异常: {type(e).__name__}: {e}")
            return ShellResult(success=False, message=f"执行异常: {type(e).__name__}: {e}", app_name=app_name)

    async def _run_command(
        self, command: str, shell: bool = False,
        app_name: str = "", app_path: str = "",
    ) -> ShellResult:
        """异步包装：将同步子进程调用放入线程池，不阻塞事件循环。"""
        return await asyncio.to_thread(
            self._run_command_sync, command, shell, app_name, app_path,
        )

    @staticmethod
    def _detect_os() -> OSType:
        system = platform.system().lower()
        if system == "windows":
            return OSType.WINDOWS
        elif system == "darwin":
            return OSType.MACOS
        return OSType.LINUX


# ── 单例 ──

_instance: Optional[LocalShellBackend] = None


def get_shell_backend(**kwargs) -> LocalShellBackend:
    global _instance
    if _instance is None:
        _instance = LocalShellBackend(**kwargs)
    return _instance
