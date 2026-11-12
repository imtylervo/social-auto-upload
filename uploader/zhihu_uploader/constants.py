"""Zhihu creator center pages and upload limits."""
from datetime import timedelta, timezone


ZHIHU_CREATOR_URL = "https://www.zhihu.com/creator"
ZHIHU_ARTICLE_URL = "https://zhuanlan.zhihu.com/write"
ZHIHU_VIDEO_URL = "https://www.zhihu.com/upload-video"
ZHIHU_MANAGE_URL = "https://www.zhihu.com/creator/manage/creation"

ZHIHU_TIMEZONE = timezone(timedelta(hours=8), "Asia/Shanghai")
ZHIHU_SCHEDULE_MINUTES = 30
ZHIHU_SCHEDULE_MAX_HOURS = 48

ZHIHU_ARTICLE_TITLE_MAX = 100
ZHIHU_VIDEO_TITLE_MIN = 5
ZHIHU_VIDEO_TITLE_MAX = 50
ZHIHU_VIDEO_DESCRIPTION_MAX = 300
ZHIHU_VIDEO_TOPICS_MAX = 10
# The page accepts a video only if size > 102400; exactly 100KB is rejected too.
ZHIHU_VIDEO_MIN_BYTES = 100 * 1024
ZHIHU_VIDEO_MAX_BYTES = 20 * 1024**3
ZHIHU_VIDEO_MAX_SECONDS = 4 * 60 * 60
ZHIHU_VIDEO_EXTENSIONS = {
    ".3gp", ".asf", ".avi", ".dat", ".f4v", ".flv", ".m4v", ".mkv", ".mov",
    ".mp4", ".mp4v", ".mpe", ".mpeg", ".mpg", ".ra", ".ram", ".rm", ".rmvb",
    ".vob", ".webm", ".wm", ".wmv",
}
ZHIHU_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".heic", ".heif", ".gif"}

# The originality declaration uses the submitted value; shared by the CLI and the upload check so the two enumerations cannot drift apart.
ZHIHU_ORIGINALITY = ("original", "reprint")

# Full text of the current field (category) and declaration menus; the CLI shows the legal values, and before submitting they are still checked against the live menu.
ZHIHU_VIDEO_CATEGORIES = (
    "人文", "体育竞技", "健康医学", "其他", "军事", "动漫", "娱乐", "宠物",
    "家居生活", "家用电器", "影视", "心理学", "情感", "故事", "教育", "数码",
    "旅行", "时尚穿搭", "母婴亲子", "汽车", "法律", "游戏电竞", "社会/时政",
    "社会学", "科学工程", "科技互联网", "经济与管理", "美妆个护", "美食",
    "职场", "艺术", "运动健身", "音乐",
)
ZHIHU_VIDEO_MARKS = (
    "内容无需标注", "含 AI 生成内容", "含虚构演绎内容", "内容含营销信息",
    "内容为转载", "个人观点仅供参考",
)
