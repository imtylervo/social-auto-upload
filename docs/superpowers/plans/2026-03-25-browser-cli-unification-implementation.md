# Browser CLI Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify the `sau` CLI contract for the three browser platforms (Douyin, Kuaishou, Xiaohongshu), add the Xiaohongshu CLI/skill, and unify the video body as `desc` and the image post body as `note`.

**Architecture:** Keep the existing single-file main entry `sau_cli.py` and do not introduce a new CLI framework. `sau_cli.py` handles the parser, request dataclasses, dispatch and account file resolution. Each platform uploader only gets the minimal field wiring. The skills, README, CLI/install/update docs and examples switch to the unified contract together, so that several sets of names are never exposed externally at once.

**Tech Stack:** Python 3.10+, `argparse`, `asyncio`, `dataclasses`, `pathlib`, `unittest`, existing Patchright-based uploaders, repository markdown docs

---

## File Structure

### New files

- `tests/test_sau_browser_cli.py`
  - Covers the unified CLI parser / dispatch / request mapping of the three browser platforms
- `skills/xiaohongshu-upload/SKILL.md`
  - Main description of the Xiaohongshu CLI skill
- `skills/xiaohongshu-upload/references/runtime-requirements.md`
  - Xiaohongshu runtime prerequisites
- `skills/xiaohongshu-upload/references/cli-contract.md`
  - Xiaohongshu CLI contract
- `skills/xiaohongshu-upload/references/troubleshooting.md`
  - Xiaohongshu troubleshooting doc
  - PowerShell example commands
  - Shell example commands
  - Python command template

### Modified files

- `sau_cli.py`
  - Add the `xiaohongshu` parser / dispatch
  - Rework the Douyin and Kuaishou request dataclasses and option model
- `uploader/douyin_uploader/main.py`
  - Wire `desc` into video
  - Wire `title + note` into image posts
- `uploader/ks_uploader/main.py`
  - Wire `desc` into video
  - Wire `title + note` into image posts
- `uploader/xiaohongshu_uploader/main.py`
  - Only the minimal field adaptation needed for the CLI wiring
- `README.md`
  - Add the Xiaohongshu CLI / skill, and unify the option descriptions of the three platforms
- `docs/CLI.md`
  - Unify the command contract of the three browser platforms
- `docs/install.md`
  - Add the Xiaohongshu CLI example and the unified option description
- `docs/update.md`
  - Add the Xiaohongshu check items and skill paths
- `skills/douyin-upload/SKILL.md`
- `skills/douyin-upload/references/cli-contract.md`
- `skills/kuaishou-upload/SKILL.md`
- `skills/kuaishou-upload/references/cli-contract.md`
- `examples/get_xiaohongshu_cookie.py`
- `examples/upload_video_to_xiaohongshu.py`

## Task 1: Lock the unified CLI contract with tests

**Files:**
- Create: `tests/test_sau_browser_cli.py`
- Reference: `sau_cli.py`

- [ ] **Step 1: Write the unified CLI parser tests**

Cover the minimal command contract in `tests/test_sau_browser_cli.py`:

```python
import asyncio
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import AsyncMock, patch

import sau_cli


class BrowserCliParserTests(unittest.TestCase):
    def test_build_parser_accepts_xiaohongshu_login(self):
        parser = sau_cli.build_parser()
        args = parser.parse_args(["xiaohongshu", "login", "--account", "creator"])
        self.assertEqual(args.platform, "xiaohongshu")
        self.assertEqual(args.action, "login")

    def test_douyin_upload_video_accepts_desc(self):
        parser = sau_cli.build_parser()
        args = parser.parse_args([
            "douyin", "upload-video",
            "--account", "creator",
            "--file", "demo.mp4",
            "--title", "title",
            "--desc", "video description",
        ])
        self.assertEqual(args.desc, "video description")

    def test_kuaishou_upload_note_accepts_title_and_note(self):
        parser = sau_cli.build_parser()
        args = parser.parse_args([
            "kuaishou", "upload-note",
            "--account", "creator",
            "--images", "1.png",
            "--title", "image post title",
            "--note", "image post body",
        ])
        self.assertEqual(args.title, "image post title")
        self.assertEqual(args.note, "image post body")
```

- [ ] **Step 2: Write the dispatch routing tests**

Continue in `tests/test_sau_browser_cli.py` with the minimal dispatch checks:

```python
class BrowserCliDispatchTests(unittest.TestCase):
    def test_dispatch_xiaohongshu_check_prints_valid(self):
        args = Namespace(platform="xiaohongshu", action="check", account="creator")
        with patch("sau_cli.check_xiaohongshu_account", new=AsyncMock(return_value=True)):
            code = asyncio.run(sau_cli.dispatch(args))
        self.assertEqual(code, 0)

    def test_dispatch_douyin_upload_note_uses_new_request_fields(self):
        args = Namespace(
            platform="douyin",
            action="upload-note",
            account="creator",
            images=[Path("1.png")],
            title="image post title",
            note="image post body",
            tags="test,image-post",
            schedule=0,
            debug=False,
            headless=True,
        )
        with patch("sau_cli.upload_note", new=AsyncMock()) as mock_upload:
            asyncio.run(sau_cli.dispatch(args))
        request = mock_upload.await_args.args[0]
        self.assertEqual(request.title, "image post title")
        self.assertEqual(request.note, "image post body")
```

- [ ] **Step 3: Run the tests first and confirm they fail**

Run:

```powershell
py -3 -m unittest tests.test_sau_browser_cli -v
```

Expected:

- Fails because `sau_cli.py` does not have the `xiaohongshu` branch and the unified fields yet

- [ ] **Step 4: Commit the test scaffolding**

```powershell
git add tests/test_sau_browser_cli.py
git commit -m "test: define browser cli unification contract"
```

## Task 2: Change `sau_cli.py` to add the unified options and Xiaohongshu routing

**Files:**
- Modify: `sau_cli.py`
- Reference: `uploader/xiaohongshu_uploader/main.py`
- Reference: `uploader/douyin_uploader/main.py`
- Reference: `uploader/ks_uploader/main.py`

- [ ] **Step 1: Add the Xiaohongshu request dataclasses**

Add to `sau_cli.py`:

```python
@dataclass(slots=True)
class XiaohongshuVideoUploadRequest:
    account_name: str
    video_file: Path
    title: str
    description: str
    tags: list[str]
    publish_date: datetime | int
    thumbnail_file: Path | None = None
    publish_strategy: str = XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE
    debug: bool = True
    headless: bool = True


@dataclass(slots=True)
class XiaohongshuNoteUploadRequest:
    account_name: str
    image_files: list[Path]
    title: str
    note: str
    tags: list[str]
    publish_date: datetime | int
    publish_strategy: str = XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE
    debug: bool = True
    headless: bool = True
```

- [ ] **Step 2: Rework the Douyin and Kuaishou request dataclasses**

Unify the fields to the following model:

```python
class DouyinVideoUploadRequest:
    title: str
    description: str

class DouyinNoteUploadRequest:
    title: str
    note: str

class KuaishouVideoUploadRequest:
    title: str
    description: str

class KuaishouNoteUploadRequest:
    title: str
    note: str
```

Requirements:

- Video uses `description`
- Image post uses `note`
- Stop designing the image post request with only the legacy `note` semantics and no `title`

- [ ] **Step 3: Change the parser**

In `build_parser()`, do the following:

- Add `--desc` to `douyin upload-video`
- Add `--desc` to `kuaishou upload-video`
- Change `douyin upload-note` to `--title --note`
- Change `kuaishou upload-note` to `--title --note`
- Add the whole `xiaohongshu` set:
  - `login`
  - `check`
  - `upload-video --title --desc --tags --thumbnail`
  - `upload-note --images --title --note --tags`

- [ ] **Step 4: Add the Xiaohongshu account functions**

Add to `sau_cli.py`:

```python
async def login_xiaohongshu_account(account_name: str, headless: bool = True) -> dict: ...
async def check_xiaohongshu_account(account_name: str) -> bool: ...
async def upload_xiaohongshu_video(request: XiaohongshuVideoUploadRequest) -> Path: ...
async def upload_xiaohongshu_note(request: XiaohongshuNoteUploadRequest) -> Path: ...
```

Requirements:

- The account path keeps going through `resolve_account_file("xiaohongshu", account_name)`
- Login / check reuse `xiaohongshu_setup` and `cookie_auth` respectively
- Validate with `setup(handle=False)` before uploading

- [ ] **Step 5: Change dispatch**

Requirements:

- All three browser platforms print the same output:
  - On a successful `login`, print the account file path
  - `check` prints `valid` / `invalid`
  - `upload-video` prints a short summary
  - `upload-note` prints a summary of the image count
- Request construction is mapped uniformly:
  - Video: `title + description`
  - Image post: `title + note`

- [ ] **Step 6: Run the CLI tests and confirm they pass**

Run:

```powershell
py -3 -m unittest tests.test_sau_browser_cli -v
```

Expected:

- `BrowserCliParserTests`
- `BrowserCliDispatchTests`

All pass

- [ ] **Step 7: Run the minimal help self-check**

Run:

```powershell
py -3 sau_cli.py douyin --help
py -3 sau_cli.py kuaishou --help
py -3 sau_cli.py xiaohongshu --help
py -3 sau_cli.py xiaohongshu upload-note --help
```

Expected:

- The Xiaohongshu subcommands exist
- The image post command shows `--title` and `--note`
- The video command shows `--desc`

- [ ] **Step 8: Commit the CLI main line**

```powershell
git add sau_cli.py tests/test_sau_browser_cli.py
git commit -m "feat: unify browser cli contracts"
```

## Task 3: Do the minimal field wiring for the uploaders

**Files:**
- Modify: `uploader/douyin_uploader/main.py`
- Modify: `uploader/ks_uploader/main.py`
- Modify: `uploader/xiaohongshu_uploader/main.py`
- Modify: `tests/test_xiaohongshu_uploader.py`

- [ ] **Step 1: Wire `desc` into Douyin video**

Add the `desc` parameter and `self.desc` to `DouYinVideo.__init__()`, and change the publish page fill-in logic to:

```python
await self.fill_title_and_description(page, self.title, self.desc or self.title, self.tags)
```

- [ ] **Step 2: Wire `title + note` into Douyin image posts**

Add the `title` parameter to `DouYinNote.__init__()`, keep `note` as the image post body, and change the publish page fill-in to:

```python
await self.fill_title_and_description(page, self.title, self.note, self.tags)
```

Requirements:

- `title` is required
- `note` is optional but should preferably be non-empty. If the existing logic requires it to be non-empty, keep that validation

- [ ] **Step 3: Wire `desc` into Kuaishou video**

Add the `desc` parameter and `self.desc` to `KSVideo.__init__()`, and when filling in the 描述 (Description) area, change it to:

```python
await page.keyboard.type(self.desc or self.title)
```

- [ ] **Step 4: Wire `title + note` into Kuaishou image posts**

Add the `title` parameter and `self.title` to `KSNote.__init__()`, and keep `self.note` as the body.

Requirements:

- Add `title` as required in the image post upload validation
- If the page currently has only a body input area and no separate title area, still keep the `title` field at the CLI / request / constructor layers, so that later platform alignment is possible

- [ ] **Step 5: Check whether the Xiaohongshu CLI wiring needs extra adaptation**

Confirm that `XiaoHongShuVideo` / `XiaoHongShuNote` only need the following mapping:

```python
title=request.title
desc=request.description  # video
desc=request.note         # image post
```

If `XiaoHongShuNote` still keeps legacy `note` compatibility, do not delete it. Just keep the CLI layer preferring `title + note + tags`.

- [ ] **Step 6: Add a Xiaohongshu mapping test**

Add a minimal assertion to `tests/test_xiaohongshu_uploader.py`:

```python
def test_note_title_defaults_do_not_override_explicit_title(self):
    app = xhs_main.XiaoHongShuNote(
        image_paths=["a.png"],
        note="body",
        tags=[],
        publish_date=0,
        account_file="account.json",
        title="explicit title",
        desc="image post body",
    )
    self.assertEqual(app.title, "explicit title")
    self.assertEqual(app.desc, "image post body")
```

- [ ] **Step 7: Run the uploader-related tests**

Run:

```powershell
py -3 -m unittest tests.test_xiaohongshu_uploader -v
```

Expected:

- The Xiaohongshu uploader unit tests pass

- [ ] **Step 8: Commit the uploader wiring**

```powershell
git add uploader/douyin_uploader/main.py uploader/ks_uploader/main.py uploader/xiaohongshu_uploader/main.py tests/test_xiaohongshu_uploader.py
git commit -m "feat: align browser uploader metadata fields"
```

## Task 4: Add the Xiaohongshu skill and update the Douyin and Kuaishou skills in step

**Files:**
- Create: `skills/xiaohongshu-upload/SKILL.md`
- Create: `skills/xiaohongshu-upload/references/runtime-requirements.md`
- Create: `skills/xiaohongshu-upload/references/cli-contract.md`
- Create: `skills/xiaohongshu-upload/references/troubleshooting.md`
- Modify: `skills/douyin-upload/SKILL.md`
- Modify: `skills/douyin-upload/references/cli-contract.md`
- Modify: `skills/kuaishou-upload/SKILL.md`
- Modify: `skills/kuaishou-upload/references/cli-contract.md`

- [ ] **Step 1: Copy the existing skill directory structure as the Xiaohongshu skeleton**

Requirements:

- Match the style of `skills/douyin-upload/`
- Prefer `sau xiaohongshu ...` by default
- State clearly that Xiaohongshu supports:
  - `login`
  - `check`
  - `upload-video`
  - `upload-note`

- [ ] **Step 2: Write the Xiaohongshu CLI contract**

State at least:

```bash
sau xiaohongshu login --account <account>
sau xiaohongshu check --account <account>
sau xiaohongshu upload-video --account <account> --file <video> --title "<title>" [--desc "..."] [--tags ...]
sau xiaohongshu upload-note --account <account> --images <img...> --title "<title>" [--note "..."] [--tags ...]
```

- [ ] **Step 3: Update the Douyin and Kuaishou skill contracts**

Requirements:

- Add `--desc` to the video example commands
- Change the image post example commands to `--title --note`
- Update all template files in step. Do not change only the docs and leave the scripts

- [ ] **Step 4: Do a file-level self-check of the skills**

Run:

```powershell
Get-ChildItem skills\xiaohongshu-upload -Recurse
Get-Content skills\douyin-upload\references\cli-contract.md
Get-Content skills\kuaishou-upload\references\cli-contract.md
```

Expected:

- The Xiaohongshu skill directory is complete
- The Douyin and Kuaishou skill contracts have both moved to the new option model

- [ ] **Step 5: Commit the skill changes**

```powershell
git add skills/xiaohongshu-upload skills/douyin-upload skills/kuaishou-upload
git commit -m "feat: add xiaohongshu skill and align browser skill contracts"
```

## Task 5: Update the examples and the README / docs

**Files:**
- Modify: `examples/get_xiaohongshu_cookie.py`
- Modify: `examples/upload_video_to_xiaohongshu.py`
- Modify: `README.md`
- Modify: `docs/CLI.md`
- Modify: `docs/install.md`
- Modify: `docs/update.md`

- [ ] **Step 1: Change the Xiaohongshu examples**

Requirements:

- `examples/get_xiaohongshu_cookie.py` clearly points to the main line `sau xiaohongshu login --account <account_name>`
- `examples/upload_video_to_xiaohongshu.py` says that the main line currently prefers the CLI
- If the direct-uploader example is kept, mark it in a comment as a "debugging entry / legacy direct path"

- [ ] **Step 2: Update the README platform table and quick start**

The README needs changes in at least these places:

- In the platform capability table, change Xiaohongshu to:
  - `CLI ✅`
  - `Skill ✅`
- Change the browser platform commands in the quick start to the unified contract
- Change the Douyin and Kuaishou image post examples to:

```bash
sau douyin upload-note --account <account_name> --images videos/1.png videos/2.png --title "Image post title" --note "Image post body"
sau kuaishou upload-note --account <account_name> --images videos/1.png videos/2.png --title "Image post title" --note "Image post body"
sau xiaohongshu upload-note --account <account_name> --images videos/1.png videos/2.png --title "Image post title" --note "Image post body"
```

- [ ] **Step 3: Update `docs/CLI.md`**

Requirements:

- Add the `xiaohongshu` section
- Write the three browser platforms up consistently:
  - Video: `title + desc + tags`
  - Image post: `title + note + tags`
- Add Xiaohongshu to the login QR code notes

- [ ] **Step 4: Update `docs/install.md` and `docs/update.md`**

Requirements:

- Add `sau xiaohongshu --help` to the install doc
- Add the Xiaohongshu self-check commands and skill paths to the update doc
- Write `account_name` consistently in the docs

- [ ] **Step 5: Check the docs and examples**

Run:

```powershell
Get-Content README.md | Select-String -Pattern "xiaohongshu|upload-note|--note|--desc" -Context 1,2
Get-Content docs\CLI.md | Select-String -Pattern "xiaohongshu|--note|--desc" -Context 1,2
Get-Content docs\install.md | Select-String -Pattern "xiaohongshu" -Context 1,2
Get-Content docs\update.md | Select-String -Pattern "xiaohongshu" -Context 1,2
```

Expected:

- The README, CLI, install and update docs all show the Xiaohongshu CLI
- The image post body is written as `--note`
- The video description is written as `--desc`

- [ ] **Step 6: Run the final minimal verification**

Run:

```powershell
py -3 -m unittest tests.test_sau_browser_cli tests.test_xiaohongshu_uploader -v
py -3 sau_cli.py xiaohongshu --help
py -3 sau_cli.py xiaohongshu upload-video --help
py -3 sau_cli.py xiaohongshu upload-note --help
```

Expected:

- The unit tests pass
- The Xiaohongshu CLI help exists
- The video command shows `--desc`
- The image post command shows `--note`

- [ ] **Step 7: Commit the wrap-up**

```powershell
git add examples/get_xiaohongshu_cookie.py examples/upload_video_to_xiaohongshu.py README.md docs/CLI.md docs/install.md docs/update.md
git commit -m "docs: align browser cli docs and examples"
```
