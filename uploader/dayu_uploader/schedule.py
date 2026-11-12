"""Time validation and native date picking shared by Dayu video and image post."""
import re
from datetime import datetime, timedelta

from patchright.async_api import BrowserContext, Page, expect

from uploader.dayu_uploader.constants import (
    DAYU_MONTH_NAMES, DAYU_SCHEDULE_MAX_DAYS, DAYU_SCHEDULE_MIN_HOURS,
    DAYU_SCHEDULE_STEP_MINUTES, DAYU_TIMEZONE,
)


async def read_dayu_schedule(context: BrowserContext, origin_id: str, expected: str | None) -> dict:
    """Read the value the server saved for the draft; when looking up an old result the future range is not checked again and the platform time is not changed."""
    response = await context.request.get("https://mp.dayu.com/dashboard/getDraftInfo",
                                         params={"draft_id": origin_id}, timeout=30000)
    if not response.ok:
        raise RuntimeError(f"Failed to query the schedule setting of the original post: HTTP {response.status}")
    data = await response.json()
    if data.get("draft_id") != origin_id:
        raise RuntimeError("The schedule query did not return this draft; the login may have expired or the API changed")
    enabled = data.get("is_timed_release")
    if expected is None:
        if enabled is not False:
            raise RuntimeError("The platform did not confirm the publish-now setting; refusing to confirm publishing")
        return {}
    target = datetime.fromisoformat(expected)
    if target.tzinfo is None:
        raise ValueError("The scheduled time in the result file must include a time zone")
    epoch = data.get("time_for_release")
    # Tested: the save API rounds the seconds hidden by the control down to the minute; compare the exact epoch, a platform shift of even one minute is not tolerated.
    if enabled is not True or isinstance(epoch, bool) or not isinstance(epoch, (int, float)):
        raise RuntimeError("The platform did not save this scheduled publishing setting")
    actual = datetime.fromtimestamp(epoch / 1000, DAYU_TIMEZONE)
    if actual != target:
        raise RuntimeError(f"The scheduled time saved by the platform does not match: expected={target.isoformat()}, actual={actual.isoformat()}")
    return {"schedule": actual.isoformat(), "schedule_verified": True}


def validate_dayu_schedule(value: datetime | None, now: datetime | None = None) -> datetime | None:
    """A CLI time without a time zone is read as Beijing time; a time with a time zone from a direct call is converted and then checked. No automatic rounding."""
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise ValueError("Dayu scheduled time must be a datetime; on the CLI use --schedule YYYY-MM-DD HH:MM")
    target = value.replace(tzinfo=DAYU_TIMEZONE) if value.tzinfo is None else value.astimezone(DAYU_TIMEZONE)
    current = now or datetime.now(DAYU_TIMEZONE)
    if current.tzinfo is None:
        raise ValueError("The current time used for validation must include a time zone")
    if target.second or target.microsecond or target.minute % DAYU_SCHEDULE_STEP_MINUTES:
        raise ValueError(f"Dayu scheduling uses {DAYU_SCHEDULE_STEP_MINUTES}-minute steps, give a time on such a step (for example 10:30)")
    if not current + timedelta(hours=DAYU_SCHEDULE_MIN_HOURS) <= target <= current + timedelta(days=DAYU_SCHEDULE_MAX_DAYS):
        raise ValueError(f"Dayu scheduled time must be between {DAYU_SCHEDULE_MIN_HOURS} hours and {DAYU_SCHEDULE_MAX_DAYS} days from now, Beijing time")
    return target


async def fill_dayu_schedule(page: Page, value: datetime | None) -> None:
    """Use the day, hour and minute options the page actually offers; for publish-now also read back the disabled state."""
    target = validate_dayu_schedule(value)
    # The normal body layout and the full-screen layout each have a copy of the setting; the visible radio container plus a direct text prefix ("定时发布" = scheduled publishing) excludes the hidden copy and other options.
    option = page.locator(".article-write_radio:visible").filter(has_text=re.compile(r"^\s*定时发布"))
    await expect(option).to_have_count(1)
    toggle = option.locator(":scope > .w-radio")
    if "w-radio_checked" in (await toggle.get_attribute("class") or ""):
        await toggle.click()
    await expect(toggle).not_to_have_class(re.compile(r"\bw-radio_checked\b"))
    # This input only shows the selected value; the click target is the mask of the same component, a direct click on the input is intercepted by the mask.
    widget = page.locator(".widgets-datepicker-m:visible")
    if target is None:
        await expect(widget).to_have_count(0)
        return
    if await page.evaluate("new Date().getTimezoneOffset()") != -480:
        raise RuntimeError("The browser used for Dayu scheduling must use the Asia/Shanghai time zone")
    await toggle.click()
    await expect(toggle).to_have_class(re.compile(r"\bw-radio_checked\b"))
    await expect(widget).to_have_count(1)
    await widget.locator(".widgets-datepicker-m_mask").click()
    # Each of the two layouts creates its own calendar instance; only the open calendar is used, and view classes tell date, hour and minute apart.
    picker = page.locator(".datetimepicker:visible")
    await expect(picker).to_have_count(1)
    days = picker.locator(".datetimepicker-days")
    heading = days.locator("th.switch")
    desired_month = f"{DAYU_MONTH_NAMES[target.month - 1]} {target.year}"
    if (await heading.inner_text()).strip() != desired_month:
        # A seven-day range crosses into the next month at most, and the next-month button is usable in that range; no loop clicking through unknown months.
        await days.locator("th.next").click()
    await expect(heading).to_have_text(desired_month)
    day = days.locator("td.day:not(.old):not(.new)").filter(has_text=re.compile(f"^{target.day}$"))
    await expect(day).not_to_have_class(re.compile(r"\bdisabled\b"))
    await day.click()
    hour = picker.locator(".datetimepicker-hours .hour").filter(has_text=re.compile(f"^{target.hour}:00$"))
    await expect(hour).not_to_have_class(re.compile(r"\bdisabled\b"))
    await hour.click()
    # The native calendar does not zero-pad hours (1:05) but the input does (01:05); the same display format cannot be used to locate minutes.
    minute = picker.locator(".datetimepicker-minutes .minute").filter(has_text=re.compile(f"^{target.hour}:{target.minute:02d}$"))
    await expect(minute).not_to_have_class(re.compile(r"\bdisabled\b"))
    await minute.click()
    await expect(picker).to_have_count(0)
    await expect(widget.locator("input")).to_have_value(target.strftime("%Y年%m月%d日 %H:%M"))  # value format shown in the input, e.g. 2026年10月17日 10:30
