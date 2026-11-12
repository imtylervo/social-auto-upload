"""Fixed options of the Dayu forms; the CLI, video and image post share one definition."""
from datetime import timedelta, timezone

# Tested: video and image post use the same scheduling control: Beijing time, at least two hours ahead, at most seven days, in five-minute steps.
DAYU_TIMEZONE = timezone(timedelta(hours=8), "Asia/Shanghai")
DAYU_SCHEDULE_MIN_HOURS = 2
DAYU_SCHEDULE_MAX_DAYS = 7
DAYU_SCHEDULE_STEP_MINUTES = 5
DAYU_MONTH_NAMES = ("一月", "二月", "三月", "四月", "五月", "六月", "七月", "八月", "九月", "十月", "十一月", "十二月")  # month names as the date picker shows them (January..December)

# Full category list of the current account's video form as of 2026-10-17; shared by the entry point and direct calls, invalid values are rejected before upload.
DAYU_VIDEO_CATEGORIES = (
    "其他", "社会", "国内", "国际", "体育", "科技", "娱乐", "军事", "财经", "汽车",
    "房产", "时尚", "健康", "两性情感", "游戏", "动漫", "旅游", "美食", "历史", "奇闻",
    "科学探索", "星座", "育儿", "教育", "美女", "搞笑", "演讲", "萌娃", "萌宠", "音乐",
    "语言类", "记录短片", "涨姿势", "劲爆体育", "幽默", "综艺", "电视剧", "电影", "纪录片",
    "少儿", "文化", "三农", "生活方式",
)
# "转载" (reprint) makes extra fields required; it has its own name so call sites do not repeat the business value.
DAYU_SOURCE_REPRINT = "转载"
DAYU_SOURCE_TYPES = ("无需标注", "AI生成", "虚构演绎", "营销信息", DAYU_SOURCE_REPRINT, "个人观点", "不适宜未成年人")

# Tested on the management page: 1 = public, 3 = under review after submission; both confirm the post was submitted, drafts are neither.
DAYU_CONTENT_PUBLIC = 1
DAYU_CONTENT_REVIEWING = 3
# After a real scheduled submission the management page shows "待发布" (pending publish), the content API returns status=5, and _app_extra holds the saved time.
DAYU_CONTENT_SCHEDULED = 5
