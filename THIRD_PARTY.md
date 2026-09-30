# 第三方依赖

本项目直接依赖以下项目；其许可证随安装包或对应仓库保留。

| 项目 | 使用方式 | 版本或提交 | 许可证 |
| --- | --- | --- | --- |
| [aoguai/pyJianYingDraft](https://github.com/aoguai/pyJianYingDraft) | 音频片段构建、草稿 codec、登记字段生成 | `2b6ed48b0f096e5a76a5b8a68a6d7d233defb463` | Apache-2.0 |
| [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) | MCP stdio 服务与客户端测试 | `1.30.0`，由 uv.lock 固定 | MIT |

pyJianYingDraft fork 的 codec 来源说明指向 [wenshui330/jy-draftc](https://github.com/wenshui330/jy-draftc)，原项目本轮没有作为独立二进制安装。原生运行时只使用用户本机安装的剪映，不包含剪映程序、DLL 或素材库。

[mcncarl/jianying-headless](https://github.com/mcncarl/jianying-headless) 与配套 yichen Skill 仅用于方案调研，没有复制或安装其实现。它要求特定 macOS 环境，未作为 Windows 项目依赖。

其余传递依赖及精确版本见 `uv.lock`，许可证以各依赖自身的许可证文件为准。
