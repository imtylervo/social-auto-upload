"""Beijing-time scheduling for Zhihu articles and videos."""
from datetime import datetime, timedelta
import re

from patchright.async_api import Page, expect

from uploader.zhihu_uploader.constants import (
    ZHIHU_SCHEDULE_MAX_HOURS, ZHIHU_SCHEDULE_MINUTES, ZHIHU_TIMEZONE,
)


def validate_zhihu_schedule(value: datetime | None, now: datetime | None = None) -> datetime | None:
    """Check the time against the range the page actually supports; CLI input without a time zone is read as Beijing time."""
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise ValueError("Zhihu scheduled time must be a datetime; on the CLI use --schedule YYYY-MM-DD HH:MM")
    target = value.replace(tzinfo=ZHIHU_TIMEZONE) if value.tzinfo is None else value.astimezone(ZHIHU_TIMEZONE)
    current = now or datetime.now(ZHIHU_TIMEZONE)
    if current.tzinfo is None:
        raise ValueError("The clock used to validate the Zhihu schedule must include a time zone")
    if target.second or target.microsecond:
        raise ValueError("Zhihu scheduling is precise to the minute; seconds or microseconds are not accepted")
    if not current + timedelta(minutes=ZHIHU_SCHEDULE_MINUTES) <= target <= current + timedelta(hours=ZHIHU_SCHEDULE_MAX_HOURS):
        raise ValueError("Zhihu scheduled time must be between 30 minutes and 48 hours from now, Beijing time")
    return target


async def fill_zhihu_article_schedule(page: Page, value: datetime | None) -> None:
    """Fill in the schedule with the date, hour and minute pickers of the article publish panel, and read it back."""
    target = validate_zhihu_schedule(value)
    if target is None:
        return

    # The article form has "定时发布" (scheduled publishing) as a separate switch; clicking it opens the schedule panel observed on the page.
    await page.get_by_text("定时发布", exact=True).click()
    panel_label = page.get_by_text("开启定时发布", exact=True)  # "开启定时发布" = enable scheduled publishing
    await expect(panel_label).to_be_visible()
    picker = page.locator(".DateTimePicker")
    await expect(picker).to_have_count(1)
    date_button = page.locator(".DatePicker-Button")
    await expect(date_button).to_have_count(1)
    shown_date = await date_button.inner_text()
    if shown_date != target.strftime("%Y-%m-%d"):
        await date_button.click()
        calendar = page.locator(".Calendar")
        await expect(calendar).to_be_visible()
        shown_month = (await calendar.locator(".Calendar-topToolDate").inner_text()).strip()
        wanted_month = f"{target.year} 年 {target.month} 月"  # calendar header, e.g. "2026 年 10 月"
        if shown_month != wanted_month:
            # A 48-hour range crosses into the adjacent month at most; the button role classes come from the actual calendar DOM on the page.
            await calendar.locator(".Calendar-topToolButton--nextMonth").click()
        await expect(calendar.locator(".Calendar-topToolDate")).to_have_text(wanted_month)
        day = calendar.locator("td.Calendar-day:not(.is-disabled):not(.is-not-this-month)").filter(
            has_text=re.compile(rf"^{target.day}$"),
        )
        await expect(day).to_have_count(1)
        await day.click()
        await expect(date_button).to_have_text(target.strftime("%Y-%m-%d"))

    # The page splits hour and minute into two dropdowns of the same structure; the DOM order was verified on the actual popup.
    time_selects = picker.locator(".Select-button")
    await expect(time_selects).to_have_count(2)
    await time_selects.nth(0).click()
    hour = page.get_by_role("option", name=f"{target.hour:02d}", exact=True)
    await expect(hour).to_have_count(1)
    if not await hour.is_enabled():
        raise RuntimeError("The Zhihu schedule hour option cannot be selected now; check the time range")
    await hour.click()
    await time_selects.nth(1).click()
    minute = page.get_by_role("option", name=f"{target.minute:02d}", exact=True)
    await expect(minute).to_have_count(1)
    if not await minute.is_enabled():
        raise RuntimeError("The Zhihu schedule minute option cannot be selected now; check the time range")
    await minute.click()
    await expect(time_selects.nth(0)).to_have_text(f"{target.hour:02d}")
    await expect(time_selects.nth(1)).to_have_text(f"{target.minute:02d}")
    confirm = page.get_by_role("button", name="确认", exact=True)  # "确认" = Confirm
    await expect(confirm).to_be_enabled()
    await confirm.click()
    await expect(panel_label).to_have_count(0)


async def fill_zhihu_video_schedule(page: Page, value: datetime | None) -> None:
    """Enable and read back the date and time in the video form's own scheduling area."""
    target = validate_zhihu_schedule(value)
    if target is None:
        return
    schedule = page.locator(".VideoUploadForm-scheduledPublish")
    await expect(schedule).to_have_count(1)
    # The video page script mounts this component inside the VideoUploadForm-scheduledPublish row.
    toggle = schedule.locator('input[type="checkbox"]')
    await expect(toggle).to_have_count(1)
    if not await toggle.is_checked():
        await toggle.check()
    picker = schedule.locator(".DateTimePicker")
    await expect(picker).to_be_visible()
    date_button = picker.locator(".DatePicker-Button")
    await expect(date_button).to_have_count(1)
    shown_date = await date_button.inner_text()
    if shown_date != target.strftime("%Y-%m-%d"):
        await date_button.click()
        calendar = page.locator(".Calendar")
        await expect(calendar).to_be_visible()
        shown_month = (await calendar.locator(".Calendar-topToolDate").inner_text()).strip()
        wanted_month = f"{target.year} 年 {target.month} 月"  # calendar header
        if shown_month != wanted_month:
            await calendar.locator(".Calendar-topToolButton--nextMonth").click()
        await expect(calendar.locator(".Calendar-topToolDate")).to_have_text(wanted_month)
        day = calendar.locator("td.Calendar-day:not(.is-disabled):not(.is-not-this-month)").filter(
            has_text=re.compile(rf"^{target.day}$"),
        )
        await expect(day).to_have_count(1)
        await day.click()
        await expect(date_button).to_have_text(target.strftime("%Y-%m-%d"))
    time_selects = picker.locator(".Select-button")
    await expect(time_selects).to_have_count(2)
    await time_selects.nth(0).click()
    hour = page.get_by_role("option", name=f"{target.hour:02d}", exact=True)
    await expect(hour).to_have_count(1)
    if not await hour.is_enabled():
        raise RuntimeError("The Zhihu schedule hour option cannot be selected now; check the time range")
    await hour.click()
    await time_selects.nth(1).click()
    minute = page.get_by_role("option", name=f"{target.minute:02d}", exact=True)
    await expect(minute).to_have_count(1)
    if not await minute.is_enabled():
        raise RuntimeError("The Zhihu schedule minute option cannot be selected now; check the time range")
    await minute.click()
    await expect(time_selects.nth(0)).to_have_text(f"{target.hour:02d}")
    await expect(time_selects.nth(1)).to_have_text(f"{target.minute:02d}")
