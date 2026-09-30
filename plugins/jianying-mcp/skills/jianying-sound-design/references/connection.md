# 本地连接

插件用于 Windows 本机 Codex，底层 MCP 是 stdio 进程。插件包含技能与启动配置；Python 环境、剪映安装目录和草稿路径由仓库根目录的 `install-plugin.ps1` 配置。它不是已部署的网页版 ChatGPT 远程接口。

已配置本项目时，在仓库根目录运行 `./install-plugin.ps1`。新电脑先克隆仓库，再运行脚本并提供 `-InstallDir`；需要时同时指定 `-DraftRoot` 和 `-UserData`。脚本复用 setup、登记插件源、安装插件并验证 MCP 握手，不编辑剪映工程。完成后重启 Codex，开新聊天使用。

启动配置读取 `%LOCALAPPDATA%/jianying-mcp/runtime.json`，其中保存本机 Python、入口和配置文件的绝对路径。因此插件缓存位置或当前工作目录变化不影响启动，不需要公开用户路径。仓库移动后重跑安装脚本更新这个指针。

没有连接时，不要退回截图或鼠标操作。先检查启动指针、运行环境和 doctor。当前聊天如果尚未重新加载插件，可在仓库通过 `.venv/Scripts/python.exe -m jianying_bridge.cli` 使用同一套能力，`guide` 可读取相同经验；准备计划、构建与登记子命令见仓库 README。

已缓存音效只在本机读取，插件不下载会员资源，也不保存账号凭据。真实草稿、字幕全文、音频、计划和配置备份都不属于插件发布内容。
