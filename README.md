# jianying-mcp

Windows 剪映专业版的本地 **MCP + CLI** 接入：读取已有工程，复制工程，追加可编辑音效轨道，再登记到剪映首页。保留原轨道、字幕、关键帧、画布配置和未知原生字段。

可以使用自己的音频，也可以按名称查找剪映已下载到本机的内置音效。默认把音效作为多个可编辑片段放在同一条轨道，之后可以继续在剪映里拖动、裁剪、分别调音量；也支持按明确指定的 ID 合并已有音频轨道。整个流程通过草稿文件完成，无需截图、鼠标控制或 Computer Use。

仓库还提供 **「剪映音效助手」Codex 插件**，把 MCP 与实际剪辑经验一起安装。插件会指导助手选择音效、安排字幕时间锚点、控制密度和音量、保留已有调整，并把音效整理到同一条轨道。经验也可单独通过 MCP 或 CLI 按需读取。

## 兼容范围

- 本机实测：Windows 剪映 `11.5.0.14471`、64 位 Python `3.13`。
- 新版加密草稿通过隔离进程调用用户自己安装的 `videoeditor.dll`；项目不分发剪映程序或 DLL。
- 支持 `draft_content.json` / `draft_info.json`，并识别 `Timelines/project.json` 指定的主时间线。
- 内置音效查询只读取本机已缓存资源，不联网下载，不调整会员状态；未缓存音效需要先在剪映里下载。
- 当前是工程副本编辑流程。剪映退出后登记副本、重新打开，时间线才会显示新增音效。
- 当前不提供原生自动导出，也不能让网页版 ChatGPT 直接启动本机 stdio 进程。适用于 Codex 等支持本地 stdio MCP 的客户端。

2026-09-30 的真实多时间线工程测试保留了 337 个原片段和 679 项素材数据，新增 19 条音效轨道，副本通过加密往返、文件路径、轨道保留及首页登记检查。随后检查剪映重新保存过的文件，原片段时间和 336 条字幕内容保留，19 条音效的素材、音量及淡入淡出仍在；新增片段被对齐到视频帧，最大偏移约 13 毫秒。还从保存后的副本生成了未发布的再次编辑测试工程。播放听感与界面操作仍需用户验收；这些结果不代表所有版本或所有复杂工程均已兼容。

## 安装

需要 Windows、64 位 Python 3.11+、[uv](https://docs.astral.sh/uv/getting-started/installation/) 和自己安装的剪映专业版。

```powershell
git clone https://github.com/jedliuai/jianying-mcp.git
cd jianying-mcp
.\setup.ps1 -InstallDir 'D:\Program Files\JianyingPro\具体版本目录' -DraftRoot 'D:\剪映草稿'
```

`InstallDir` 指向含 `videoeditor.dll` 的版本目录；`DraftRoot` 是剪映设置里的草稿位置。依赖由 `uv.lock` 固定，其中 pyJianYingDraft 锁定到指定 fork 的 Git 提交，不能随意换成同名 PyPI 包。

路径写入忽略的 `local.config.json`。也可以设置 `JIANYING_BRIDGE_CONFIG` 指向另一份配置，或用 `JIANYING_DRAFT_ROOT`、`JIANYING_INSTALL_DIR` 覆盖路径。

## 接入 Codex

推荐安装完整插件。已有本地配置时：

```powershell
.\install-plugin.ps1
```

新电脑可以一步设置运行环境并安装插件：

```powershell
.\install-plugin.ps1 -InstallDir 'D:\Program Files\JianyingPro\具体版本目录' -DraftRoot 'D:\剪映草稿'
```

脚本通过 Codex CLI 登记 `jianying-local-plugins` 插件源并安装 `jianying-mcp`，验证安装副本的 MCP 握手、工程列表和音效指南，然后移除指向同一运行环境的旧独立 `jianying-local` 配置，避免重复工具。配置修改前自动备份；需要并存时使用 `-KeepStandaloneMcp`。安装不修改剪映工程。

重启 Codex、开新聊天后可使用「剪映音效助手」和 `jianying-sound-design` 技能。可直接说：

> 使用剪映音效助手，给这个工程适量补充音效，放在一条轨道上，保留已经调整过的位置和音量。

插件目录在 `plugins/jianying-mcp/`，技能负责编辑流程，`get_jianying_sound_design_guide` 按需提供四类预设与经验。口播录屏可先参考每分钟 2～4 处提示；这只是起点，素材音量、声音密度和时间点都应按视频内容与用户反馈调整。

安装脚本把运行指针写到本机 `%LOCALAPPDATA%/jianying-mcp/runtime.json`，插件据此使用 Python、入口与配置的绝对路径，不依赖聊天工作目录或插件缓存目录。移动仓库后重跑安装脚本。Python 环境和真实素材保留在本机，插件安装只复制工具元数据与技能文件。

这是 Windows 本地 Codex 插件。插件使用[官方支持的兼容清单格式](https://developers.openai.com/plugins/build/plugins)，不代表已提交到官方公共插件目录；网页版 ChatGPT 也不能直接启动本机 stdio 进程。

检查安装或卸载：

```powershell
codex plugin list --marketplace jianying-local-plugins --json
codex plugin remove jianying-mcp@jianying-local-plugins
```

只需要独立 MCP、不使用插件经验指导时，仍可用原入口：

```powershell
.\register-mcp.ps1
```

脚本通过 `codex mcp add` 注册 `jianying-local`，使用绝对路径入口，不依赖客户端工作目录。重启 Codex 后加载 MCP；CLI 可以立即使用。配置前会在忽略的 `work/config-backups/` 中备份 Codex 配置。

其他本地 MCP 客户端使用以下结构，并替换路径：

```json
{
  "mcpServers": {
    "jianying-local": {
      "command": "D:\\项目\\jianying-mcp\\.venv\\Scripts\\python.exe",
      "args": ["D:\\项目\\jianying-mcp\\run_mcp.py"],
      "env": {"PYTHONIOENCODING": "utf-8"}
    }
  }
}
```

撤销 Codex 配置：`codex mcp remove jianying-local`。

## 在聊天里使用

> 列出最近的剪映工程，读取“演示工程”的字幕时间点。搜索剪映里已经下载的转场音和提示音。

> 给“演示工程”生成一个“演示工程-音效版”副本，在模块切换和完成操作的位置加少量低音量音效，保留原轨道。

助手准备计划，生成并校验副本。用户保存原工程并正常退出剪映后，助手登记副本。启动剪映，从首页打开副本，检查画面、声音、素材和轨道，保存并重开确认。

音效时间点可以由用户指定，也可以在用户授权后根据字幕内容安排。字幕标注的操作时间不等于逐帧确认的鼠标点击时间，精确同步需要播放检查。

## CLI

在项目目录打开 PowerShell：

```powershell
.\.venv\Scripts\python.exe -m jianying_bridge.cli doctor
.\.venv\Scripts\python.exe -m jianying_bridge.cli guide
.\.venv\Scripts\python.exe -m jianying_bridge.cli list --limit 10
.\.venv\Scripts\python.exe -m jianying_bridge.cli inspect '演示工程' --segments --limit 40 --offset 0
.\.venv\Scripts\python.exe -m jianying_bridge.cli cached-audio --query '提示'
.\.venv\Scripts\python.exe -m jianying_bridge.cli audio 'D:\音效'
```

复制 `examples/sound-effects.plan.json`，替换工程名、本地音频和时间，保存为自己的计划文件：

```powershell
.\.venv\Scripts\python.exe -m jianying_bridge.cli prepare '自己的计划.json'
.\.venv\Scripts\python.exe -m jianying_bridge.cli build '<plan_id>'
.\.venv\Scripts\python.exe -m jianying_bridge.cli verify '<build_id>'
```

`build` 返回工作目录中的工程副本，尚未进入剪映首页。保存当前剪映工程并正常退出后：

```powershell
.\.venv\Scripts\python.exe -m jianying_bridge.cli publish '<build_id>'
```

`publish` 仅表示本机首页登记：复制已验证工程，追加首页记录，备份原索引。同名草稿、运行中的剪映、索引变化或校验失败都会阻止操作。

`verify` 检查工作目录中生成时的构建快照。剪映打开并保存首页副本后，会删除默认字段、补充原生字段、转换素材路径，并把片段时间对齐到视频帧；保存后的副本不应再与生成快照做严格哈希对比。继续编辑时，使用这个已保存副本的工程名重新 `inspect` / `prepare` / `build`，生成新的副本。

时间单位为秒。`volume=1` 为 100%，支持 0～2。默认使用整个音效文件，也可以用 `source_start_seconds` 和 `duration_seconds` 选择片段。音效不能延长原工程，超出结尾会报错。

计划默认 `track_mode="single"`：所有新增音效放在一条轨道，每个片段独立可编辑。时间重叠会报错，避免静默裁短或移动音效；有意叠加多个音效时，可设为 `"independent"`，每个新音效一条轨道。

已有音效分散在多条轨道时，先 `inspect` 获取 ID，再设置 `consolidate_track_ids`，明确选中需要合并的音频轨道。旧片段的时间、音量、淡入淡出、关键帧和素材引用保留；只调整所属轨道及轨道索引。未选中的原轨道保持原样，背景音乐、配音不会被自动选中。轨道静音、锁定等设置不同会拒绝合并。可以同时新增音效，也可以设 `effects=[]` 只合并，示例见 `examples/consolidate-sound-tracks.plan.json`。

## MCP 工具

| 工具 | 用途 |
| --- | --- |
| `get_jianying_sound_design_guide` | 按需读取音效密度、音量、截取、时间锚点及四类缓存素材预设 |
| `jianying_doctor` | 环境和剪映运行状态 |
| `list_jianying_drafts` | 最近草稿，紧凑列表 |
| `inspect_jianying_draft` | 轨道、时长、分页字幕和片段 |
| `list_local_sound_effects` | 用户指定目录的本地音频 |
| `find_jianying_cached_sound_effects` | 按名称查询已缓存的内置音效 |
| `prepare_sound_effects` | 检查时间、音量、淡入淡出和合轨设置，保存计划 |
| `build_sound_effects_copy` | 复制工程，追加音效，可合放单轨或合并指定音频轨道 |
| `verify_jianying_build` | 验证原轨道、素材、主时间线镜像和音频文件 |
| `publish_jianying_build` | 剪映退出后登记副本并备份索引 |

## 工程保留与数据边界

库只生成新增音频数据，再合并进原始 JSON 副本；不把整个原工程送回模板序列化器。逐项检查原片段、素材、字幕原始字符串、画布配置及未知字段。默认保留原轨道；明确指定合轨时，检查旧片段除所属轨道索引以外的全部字段不变，并验证其余原轨道不变。只有副本身份、文件路径和授权的音效相关数据发生变化。

新版主时间线、根草稿镜像和对应备份保持同步，其他时间线保留。新增音效复制进副本，每次构建采用独立素材目录，继续追加音效也不会覆盖上一轮文件。

剪映保存后可能把素材路径转换成 `##_draftpath_placeholder_<ID>_##/...`，素材目录记录也可能使用 `./...`。再次复制时会把这些工程内部路径迁移到新副本，不修改字幕字符串，且拒绝越过草稿目录的路径。

计划绑定源草稿和音效文件哈希，文件更新会使旧计划失效。本地音视频缺失、草稿中的符号链接或目录联接会阻止交付。项目不会自动终止剪映。

本机草稿、录屏、音频、资源数据库、计划、基线快照、索引备份及配置备份都应保留在忽略的 `work/` 或剪映数据目录中。内置资源查询不返回缓存中的签名 URL，不读取账号凭据，也不向 GitHub 上传缓存素材。会员状态不意味着素材可以随代码仓库再分发。

## 来源

Windows 方案使用 [aoguai/pyJianYingDraft](https://github.com/aoguai/pyJianYingDraft) 的音频构建、codec 和首页登记字段。codec 方案来源于 [jy-draftc](https://github.com/wenshui330/jy-draftc)，只调用本机已安装的剪映 DLL。本机 11.5 的实测超出上游部分声明验证范围，应独立看待。

[Jianying Headless](https://github.com/mcncarl/jianying-headless) 及其配套 yichen Skill 是最初调研方向。其公开实现要求特定 Apple Silicon Mac 环境，没有作为本项目的 Windows 依赖，也没有复制其实现。

MCP 使用[官方 Python SDK 的 v1 系列](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x)。第三方许可证与版本见 `THIRD_PARTY.md`。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tools/smoke_mcp.py
.\.venv\Scripts\python.exe tools/smoke_mcp.py --plugin '本机已安装的插件目录'
.\.venv\Scripts\python.exe tools/probe_codec.py '演示工程'
.\.venv\Scripts\python.exe tools/smoke_native.py '演示工程'
```

自动测试使用临时目录和合成素材，覆盖单轨多片段、指定轨道合并与旧音效参数保留、重叠与静音冲突拦截、未知字段保留、多时间线、源文件变化、素材缺失、保存后再次编辑、工程路径迁移及越界拦截、索引备份、运行状态拦截、资源缓存解析与签名 URL 隔离。GitHub Actions 在 Windows 上运行这些测试，不读取真实剪映工程。

插件测试另覆盖 Windows PowerShell 5.1 脚本解析、不同工作目录与中文配置路径下的真实 stdio 握手、经验指南调用和启动失败提示。缺少或移动运行环境时，会直接提示重跑安装脚本，不向 MCP stdout 写入普通日志。

`smoke_native.py` 生成未发布的测试副本，其中包含合成测试音效；不要把它当作正式成品。
