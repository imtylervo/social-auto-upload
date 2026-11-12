# Bilibili CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Bilibili the same level of `sau` CLI as Douyin and Kuaishou, a runtime mechanism that updates `biliup` automatically, the matching skill, and complete docs with an upstream acknowledgement.

**Architecture:** Keep it lightweight and do not build a large all-purpose framework. Add one Bilibili runtime module that checks GitHub Release, downloads/updates `biliup` and runs commands. `sau_cli.py` only gets the `bilibili` subcommand and option mapping. The skill, example and README/CLI/install/update docs are aligned with the existing Douyin/Kuaishou structure.

**Tech Stack:** Python 3.10+, `requests`, `argparse`, `asyncio`, `subprocess`, `pathlib`, `unittest`, GitHub Releases, existing `biliup` integration

---

## File Structure

### New files

- `uploader/bilibili_uploader/runtime.py`
  - Bilibili runtime entry
  - Handles the automatic check, download and update of `biliup`, and runs commands
- `tests/__init__.py`
  - Test package init
- `tests/test_bilibili_runtime.py`
  - Tests automatic update, download, cache reuse and runner behavior
- `tests/test_sau_bilibili_cli.py`
  - Tests the `sau bilibili` parser and dispatch behavior
- `skills/bilibili-upload/SKILL.md`
  - Main description of the Bilibili CLI skill
- `skills/bilibili-upload/references/runtime-requirements.md`
  - Runtime prerequisites and automatic download notes
- `skills/bilibili-upload/references/cli-contract.md`
  - The `sau bilibili ...` command contract
- `skills/bilibili-upload/references/troubleshooting.md`
  - Common problems and troubleshooting
  - PowerShell example commands
  - Shell example commands
  - Python call template

### Modified files

- `sau_cli.py`
  - Add the `bilibili` subcommand
  - Reuse the existing `resolve_account_file()`, `parse_tags()` and `parse_schedule()`
- `examples/get_bilibili_cookie.py`
  - Align with the new `sau bilibili login` usage
- `examples/upload_video_to_bilibili.py`
  - Align with the new CLI/account file conventions
- `README.md`
  - Add Bilibili CLI usage, automatic download notes and the acknowledgement
- `docs/CLI.md`
  - Add `sau bilibili login/check/upload-video`
- `docs/install.md`
  - Add Bilibili automatic download / first-run notes
- `docs/update.md`
  - Add Bilibili automatic update behavior notes

## Task 1: Bilibili auto-update runtime

**Files:**
- Create: `uploader/bilibili_uploader/runtime.py`
- Create: `tests/__init__.py`
- Create: `tests/test_bilibili_runtime.py`

- [ ] **Step 1: Write the Bilibili runtime tests**

Use `unittest` and cover these minimal paths:

```python
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from uploader.bilibili_uploader.runtime import (
    build_biliup_runtime_path,
    ensure_biliup_binary,
    run_biliup_command,
)


class BiliupRuntimeTests(unittest.TestCase):
    def test_build_biliup_runtime_path_returns_platform_path(self):
        path = build_biliup_runtime_path("Windows")
        self.assertTrue(str(path).endswith("biliup.exe"))

    @patch("uploader.bilibili_uploader.runtime.fetch_latest_release")
    def test_ensure_biliup_binary_downloads_when_missing(self, mock_release):
        mock_release.return_value = {
            "tag_name": "v1.0.0",
            "asset_url": "https://example.invalid/biliup.exe",
            "asset_name": "biliup.exe",
        }
        with patch("uploader.bilibili_uploader.runtime.download_biliup_asset") as mock_download:
            ensure_biliup_binary(force_check=True)
        mock_download.assert_called_once()

    @patch("uploader.bilibili_uploader.runtime.fetch_latest_release")
    def test_ensure_biliup_binary_reuses_local_when_up_to_date(self, mock_release):
        mock_release.return_value = {
            "tag_name": "v1.0.0",
            "asset_url": "https://example.invalid/biliup.exe",
            "asset_name": "biliup.exe",
        }
        with patch("uploader.bilibili_uploader.runtime.read_local_biliup_version", return_value="v1.0.0"):
            with patch("uploader.bilibili_uploader.runtime.download_biliup_asset") as mock_download:
                ensure_biliup_binary(force_check=True)
        mock_download.assert_not_called()

    @patch("uploader.bilibili_uploader.runtime.subprocess.run")
    def test_run_biliup_command_returns_completed_process(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="ok", stderr="")
        result = run_biliup_command(["login"])
        self.assertEqual(result.returncode, 0)
```

- [ ] **Step 2: Run the tests and confirm they fail first**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bilibili_runtime -v
```

Expected:

- Fails because `uploader.bilibili_uploader.runtime` does not exist yet

- [ ] **Step 3: Write the minimal runtime implementation**

First add these minimal functions to `uploader/bilibili_uploader/runtime.py`:

```python
def get_biliup_runtime_root() -> Path: ...
def build_biliup_runtime_path(system_name: str | None = None) -> Path: ...
def fetch_latest_release() -> dict: ...
def read_local_biliup_version() -> str | None: ...
def write_local_biliup_version(version: str) -> None: ...
def download_biliup_asset(release: dict, destination: Path) -> Path: ...
def ensure_biliup_binary(force_check: bool = True) -> Path: ...
def run_biliup_command(arguments: list[str]) -> subprocess.CompletedProcess[str]: ...
```

Constraints:

- Do not introduce a complex manifest
- Target the latest GitHub Release directly
- Store only the current version string and the binary locally
- Keep the path/network/replacement logic simple

- [ ] **Step 4: Run the runtime tests again and confirm they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bilibili_runtime -v
```

Expected:

- All `BiliupRuntimeTests` pass

- [ ] **Step 5: Commit this small step**

```powershell
git add uploader/bilibili_uploader/runtime.py tests/__init__.py tests/test_bilibili_runtime.py
git commit -m "feat: add biliup runtime bootstrap"
```

## Task 2: Connect the `sau bilibili` CLI

**Files:**
- Modify: `sau_cli.py`
- Create: `tests/test_sau_bilibili_cli.py`
- Reference: `uploader/bilibili_uploader/main.py`
- Reference: `utils/constant.py`

- [ ] **Step 1: Write the CLI parser and dispatch tests**

Cover these in `tests/test_sau_bilibili_cli.py`:

```python
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import AsyncMock, patch

import sau_cli


class BilibiliCliTests(unittest.TestCase):
    def test_build_parser_accepts_bilibili_login(self):
        parser = sau_cli.build_parser()
        args = parser.parse_args(["bilibili", "login", "--account", "creator"])
        self.assertEqual(args.platform, "bilibili")
        self.assertEqual(args.action, "login")

    def test_build_parser_requires_tid_for_upload_video(self):
        parser = sau_cli.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args([
                "bilibili", "upload-video",
                "--account", "creator",
                "--file", "demo.mp4",
                "--title", "hello",
                "--desc", "hello",
            ])

    def test_dispatch_bilibili_check_prints_valid(self):
        args = Namespace(platform="bilibili", action="check", account="creator")
        with patch("sau_cli.check_bilibili_account", new=AsyncMock(return_value=True)):
            code = asyncio.run(sau_cli.dispatch(args))
        self.assertEqual(code, 0)
```

- [ ] **Step 2: Run the tests and confirm they fail first**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_sau_bilibili_cli -v
```

Expected:

- Fails because `sau_cli.py` does not have the `bilibili` parser/dispatch branches yet

- [ ] **Step 3: Add the Bilibili request model and commands in `sau_cli.py`**

Do only the minimal wiring and keep the same style as Douyin/Kuaishou:

```python
@dataclass(slots=True)
class BilibiliVideoUploadRequest:
    account_name: str
    video_file: Path
    title: str
    description: str
    tid: int
    tags: list[str]
    publish_date: datetime | int
    debug: bool = True


async def login_bilibili_account(account_name: str) -> dict: ...
async def check_bilibili_account(account_name: str) -> bool: ...
async def upload_bilibili_video(request: BilibiliVideoUploadRequest) -> Path: ...
```

Minimum parser requirements:

- `sau bilibili login --account <name>`
- `sau bilibili check --account <name>`
- `sau bilibili upload-video --account ... --file ... --title ... --desc ... --tid ... [--tags] [--schedule]`

Minimum dispatch requirements:

- Print `valid` / `invalid` like the other platforms
- Print a short summary after a successful upload

- [ ] **Step 4: Reuse the existing Bilibili option semantics**

In the Bilibili wrapper, reuse the existing project concepts directly:

- `tid` is required
- `tags` uses the existing `parse_tags()`
- `schedule` reuses the existing `parse_schedule()`
- `account` still gets the in-project account path through `resolve_account_file("bilibili", account_name)`

- [ ] **Step 5: Run the CLI tests again and confirm they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_sau_bilibili_cli -v
```

Expected:

- `BilibiliCliTests` pass

- [ ] **Step 6: Do an integration check**

Run:

```powershell
.\.venv\Scripts\python.exe sau_cli.py bilibili --help
.\.venv\Scripts\python.exe sau_cli.py bilibili upload-video --help
```

Expected:

- `login` / `check` / `upload-video` are visible
- `--tid` is shown as required in `upload-video`

- [ ] **Step 7: Commit this small step**

```powershell
git add sau_cli.py tests/test_sau_bilibili_cli.py
git commit -m "feat: add bilibili cli commands"
```

## Task 3: Add the skill and the example

**Files:**
- Create: `skills/bilibili-upload/SKILL.md`
- Create: `skills/bilibili-upload/references/runtime-requirements.md`
- Create: `skills/bilibili-upload/references/cli-contract.md`
- Create: `skills/bilibili-upload/references/troubleshooting.md`
- Modify: `examples/get_bilibili_cookie.py`
- Modify: `examples/upload_video_to_bilibili.py`

- [ ] **Step 1: Build the Bilibili skill on the Douyin/Kuaishou skill structure**

Requirements:

- The `SKILL.md` style matches the two existing skills
- Prefer `sau bilibili ...` by default
- State clearly that "the program prepares `biliup` automatically"

- [ ] **Step 2: Write the example command file**

The example commands should include at least:

```powershell
sau bilibili login --account creator
sau bilibili check --account creator
sau bilibili upload-video --account creator --file .\videos\demo.mp4 --title "demo" --desc "demo" --tid 249 --tags football,test
```

- [ ] **Step 3: Change the local examples**

Make these examples clearly move to the new entry or the new conventions:

- `examples/get_bilibili_cookie.py`
- `examples/upload_video_to_bilibili.py`

Requirements:

- Stop making users guess the `biliup.exe` path by hand
- State clearly that `sau bilibili ...` is now the recommended path
- Keep the `VideoZoneTypes` usage example

- [ ] **Step 4: Do a file-level self-check**

Run:

```powershell
Get-ChildItem skills\bilibili-upload -Recurse
Get-Content examples\get_bilibili_cookie.py
Get-Content examples\upload_video_to_bilibili.py
```

Expected:

- The Bilibili skill directory is complete
- The example content has moved to the new CLI/description

- [ ] **Step 5: Commit this small step**

```powershell
git add skills/bilibili-upload examples/get_bilibili_cookie.py examples/upload_video_to_bilibili.py
git commit -m "feat: add bilibili upload skill"
```

## Task 4: Add docs and the upstream acknowledgement

**Files:**
- Modify: `README.md`
- Modify: `docs/CLI.md`
- Modify: `docs/install.md`
- Modify: `docs/update.md`

- [ ] **Step 1: Add the Bilibili CLI usage to the README**

State at least:

- `sau bilibili login`
- `sau bilibili check`
- `sau bilibili upload-video`
- Automatic download / automatic update of `biliup`

- [ ] **Step 2: Add the command contract to the CLI docs**

Write the Bilibili section in the same style as Douyin/Kuaishou:

- Option table
- `tid` is required
- The behavior of `schedule`

- [ ] **Step 3: Explain the automatic download mechanism in the install/update docs**

Add at least these notes:

- Users do not need to install `biliup` themselves
- The first run downloads it automatically
- Later runs check for updates automatically

- [ ] **Step 4: Add thanks to the upstream project and a note about what is borrowed**

Add a clear statement in the README, at least:

- The Bilibili capability is based on `biliup`
- Thanks to / reuse of the upstream project
- The project address

Suggested wording:

```markdown
## Acknowledgements

The Bilibili upload capability of this project is integrated and wrapped on top of the open-source project `biliup`.
Thanks to the `biliup` project and its contributors for the foundation:

- https://github.com/biliup/biliup
```

- [ ] **Step 5: Check the docs**

Run:

```powershell
Get-Content README.md | Select-String -Pattern "bilibili|biliup|致谢" -Context 1,2
Get-Content docs\CLI.md | Select-String -Pattern "bilibili" -Context 1,3
Get-Content docs\install.md | Select-String -Pattern "bilibili|biliup" -Context 1,2
Get-Content docs\update.md | Select-String -Pattern "bilibili|biliup" -Context 1,2
```

Expected:

- The README, CLI, install and update docs all contain the new Bilibili content
- The README has a clear upstream acknowledgement

- [ ] **Step 6: Run the final verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bilibili_runtime tests.test_sau_bilibili_cli -v
.\.venv\Scripts\python.exe sau_cli.py bilibili --help
.\.venv\Scripts\python.exe sau_cli.py bilibili upload-video --help
```

Expected:

- The unit tests pass
- The Bilibili CLI help works
- `upload-video` shows `--tid` as required

- [ ] **Step 7: Commit the wrap-up**

```powershell
git add README.md docs/CLI.md docs/install.md docs/update.md
git commit -m "docs: add bilibili cli guidance and attribution"
```
