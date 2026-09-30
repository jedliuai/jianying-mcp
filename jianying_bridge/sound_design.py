"""Sound-design guidance distilled from user-reviewed Jianying edits."""
from copy import deepcopy


GUIDE = {
    "profile": "screen_demo",
    "purpose": "口播、录屏和软件演示：用短音效提示操作、完成反馈、章节变化与重点，保持人声清楚。",
    "track_layout": {
        "default": "single",
        "editable": "同轨多个独立片段，保留每个音效的时间、音量、淡入淡出及素材引用。",
        "existing": "从 inspect 选择已有音效轨道 ID，传 consolidate_track_ids；不自动选择配音或背景音乐。",
        "overlap": "调整新增位置避免重叠；确需叠加时选 independent，不擅自截短或移动已有音效。",
    },
    "placement": [
        "模块切换和新的演示阶段用短转场；避免给每一条字幕加音效。",
        "打开、点击、编辑、切换指标等操作用短弹出声；字幕只是时间锚点，精确点击需播放确认。",
        "解析、录入、登录或导出完成用完成提示；使用实际完成时刻，不把整段操作都铺满。",
        "关键数据、效率提升和价值点用轻提示；密集强调会削弱重点。",
        "保留用户已认可或调整的旧音效，只补充确有信息作用的位置。",
    ],
    "density": {
        "starting_point": "长篇口播录屏可先参考每分钟 2～4 个音效，再按操作密度和用户偏好调整。",
        "reviewed_example": "一次约 14 分钟的演示，19 处被评价偏少；增加到 47 处并合成单轨后获得认可。",
        "limit": "这个数量是一次经验，不是所有视频的固定配额；说明性口播可留出长段安静区域。",
    },
    "mix": {
        "starting_volume": "下列已试听素材以 7.5%～10% 音量起步；其他素材应根据自身响度和人声调整。",
        "fades": "短淡入避免突兀，淡出避免截断；淡入淡出总时长不得超过片段时长。",
        "trim": "检查素材开头的静音和有效发声范围，再设 source_start_seconds；不要只按文件起点对齐。",
    },
    "cached_presets": [
        {"role": "click", "search_title": "啵1", "duration_seconds": .3,
         "source_start_seconds": 0, "volume": .08, "fade_in_seconds": .008,
         "fade_out_seconds": .06, "anchor_offset_seconds": -.05},
        {"role": "transition", "search_title": "“呼”的转场音效", "duration_seconds": 1.1,
         "source_start_seconds": .2, "volume": .075, "fade_in_seconds": .04,
         "fade_out_seconds": .2, "anchor_offset_seconds": -.1},
        {"role": "complete", "search_title": "任务完成", "duration_seconds": 1.15,
         "source_start_seconds": .18, "volume": .08, "fade_in_seconds": .025,
         "fade_out_seconds": .25, "anchor_offset_seconds": -.07},
        {"role": "highlight", "search_title": "Ding，可爱提示音", "duration_seconds": 1.28,
         "source_start_seconds": .02, "volume": .075, "fade_in_seconds": .03,
         "fade_out_seconds": .3, "anchor_offset_seconds": -.03},
    ],
    "preset_usage": [
        "通过 find_jianying_cached_sound_effects 按名称找到实际本地文件，再填 path；预设不是素材下载链接。",
        "预设的 role、search_title、anchor_offset_seconds 不属于 effects 字段，传 prepare 前移除。",
        "start_seconds = max(0, 字幕或画面锚点 + anchor_offset_seconds)，并检查不超过工程结尾。",
        "未缓存目标音效时选本机已缓存的相近素材，或由用户提供音频；不调用会员私有接口下载。",
    ],
    "verification": [
        "原工程保持不变；生成新副本，检查原片段、字幕、素材路径、时长和音效片段。",
        "publish 前确认剪映已保存并退出；已有退出答复且 doctor 确认未运行时，无需重复确认。",
        "verify 校验生成快照；剪映保存后的副本会整理字段和按帧取整，不再和旧快照做完整哈希比较。",
        "继续编辑使用最近保存的副本作为新源，支持占位符与工程内相对素材路径。",
        "结构检查不能替代试听；报告位置来自字幕推断，便于用户逐片段微调。",
    ],
}


def sound_design_guide():
    return deepcopy(GUIDE)
