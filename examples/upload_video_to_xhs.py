import configparser
from pathlib import Path
from time import sleep

from xhs import XhsClient

from conf import BASE_DIR
from utils.files_times import generate_schedule_time_next_day, get_title_and_hashtags
from uploader.xhs_uploader.main import sign_local, beauty_print

config = configparser.RawConfigParser()
config.read(Path(BASE_DIR / "uploader" / "xhs_uploader" / "accounts.ini"))


if __name__ == '__main__':
    filepath = Path(BASE_DIR) / "videos"
    # Get the video directory
    folder_path = Path(filepath)
    # Get all files in the folder
    files = list(folder_path.glob("*.mp4"))
    file_num = len(files)

    cookies = config['account1']['cookies']
    xhs_client = XhsClient(cookies, sign=sign_local, timeout=60)
    # auth cookie
    # Note: this way of validating the cookie may not be very accurate
    try:
        xhs_client.get_video_first_frame_image_id("3214")
    except:
        print("cookie expired")
        exit()

    publish_datetimes = generate_schedule_time_next_day(file_num, 1, daily_times=[16])

    for index, file in enumerate(files):
        title, tags = get_title_and_hashtags(str(file))
        # Add to the title as a supplementary title (xhs allows up to 1000 characters, so there is no harm in filling it)
        tags_str = ' '.join(['#' + tag for tag in tags])
        hash_tags_str = ''
        hash_tags = []

        # Print the video file name, title and hashtags
        print(f"Video file name: {file}")
        print(f"Title: {title}")
        print(f"Hashtag: {tags}")

        topics = []
        # Get hashtags
        for i in tags[:3]:
            topic_official = xhs_client.get_suggest_topic(i)
            if topic_official:
                topic_official[0]['type'] = 'topic'
                topic_one = topic_official[0]
                hash_tag_name = topic_one['name']
                hash_tags.append(hash_tag_name)
                topics.append(topic_one)

        hash_tags_str = ' ' + ' '.join(['#' + tag + '[话题]#' for tag in hash_tags])

        note = xhs_client.create_video_note(title=title[:20], video_path=str(file),
                                            desc=title + tags_str + hash_tags_str,
                                            topics=topics,
                                            is_private=False,
                                            post_time=publish_datetimes[index].strftime("%Y-%m-%d %H:%M:%S"))

        beauty_print(note)
        # Force a 30s sleep to avoid risk control (required)
        sleep(30)
