import os

from mcp.server.fastmcp import FastMCP

from .core import Bridge
from .sound_design import sound_design_guide

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
mcp = FastMCP("jianying-local", instructions=(
    "通过本地草稿文件编辑剪映，保留可编辑工程。音效默认同轨多片段，合并已有音效需明确轨道 ID。"
    "编排前可读取 get_jianying_sound_design_guide 获取已实践的密度、音量、素材截取与时间锚点经验。"
    "先 list/inspect，明确本地音效和时间点，"
    "再 prepare/build/verify。publish 只能在用户保存并正常退出剪映后调用。"
    "不要自动关闭剪映或覆盖原工程。用户授权后可按字幕安排音效，并说明位置来自字幕推断；"
    "精确点击同步和最终效果需播放检查。结构校验不能替代打开播放保存验收。"))


@mcp.tool()
def get_jianying_sound_design_guide() -> dict:
    """读取口播录屏音效经验、单轨规则和四类剪映缓存音效预设；按需加载，不读取草稿或修改任何文件。"""
    return sound_design_guide()


@mcp.tool()
def jianying_doctor() -> dict:
    """检查本机剪映、草稿目录、原生 codec 和运行状态。"""
    return Bridge().doctor()


@mcp.tool()
def list_jianying_drafts(limit: int = 20) -> dict:
    """列出最近的本地剪映草稿，不读取整个草稿内容。"""
    return Bridge().list_drafts(limit)


@mcp.tool()
def inspect_jianying_draft(name: str, include_segments: bool = False, limit: int = 80, offset: int = 0) -> dict:
    """读取草稿轨道和时长，可分页读取字幕及片段时间点，原文件不变。"""
    return Bridge().inspect(name, include_segments, limit, offset)


@mcp.tool()
def list_local_sound_effects(directory: str, limit: int = 100) -> dict:
    """在用户指定的目录中列出本地音效，返回可供计划引用的绝对路径。"""
    return Bridge().list_audio(directory, limit)


@mcp.tool()
def find_jianying_cached_sound_effects(query: str = "", limit: int = 80) -> dict:
    """按名称查询剪映已下载的内置音效，返回名称、资源 ID 和本地文件。可直接用于 prepare；仅本机读取，不下载素材、不调整会员状态。"""
    return Bridge().cached_sound_effects(query, limit)


@mcp.tool()
def prepare_sound_effects(source_name: str, new_name: str, effects: list[dict], track_mode: str = "single", consolidate_track_ids: list[str] | None = None) -> dict:
    """准备音效计划。每项需 path、start_seconds，可设 source_start_seconds、duration_seconds、volume(0~2)、fade_in_seconds、fade_out_seconds、label。默认 single：音效分为可编辑片段、合放一条轨道，重叠会报错；independent 每个音效一轨。consolidate_track_ids 可明确指定合并已有音频轨道，其时间、音量、淡入淡出保留；effects 可为空以只合并。时间均为秒，不能越过工程结尾。返回计划，不修改原草稿。"""
    return Bridge().prepare(source_name, new_name, effects, track_mode, consolidate_track_ids)


@mcp.tool()
def build_sound_effects_copy(plan_id: str) -> dict:
    """在工作目录生成完整工程副本，按计划合放或分放音效轨道；只合并明确指定的音频轨道，其片段设置保留，其他原轨道不变。"""
    return Bridge().build(plan_id)


@mcp.tool()
def verify_jianying_build(build_id: str) -> dict:
    """重新读取副本，验证加密格式、原轨道和素材、音效、主时间线镜像。"""
    return Bridge().verify(build_id)


@mcp.tool()
def publish_jianying_build(build_id: str) -> dict:
    """把已验证的副本登记到本机剪映首页。需用户先保存并退出剪映；备份首页索引，不覆盖已有草稿，不发布到互联网。"""
    return Bridge().publish(build_id)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
