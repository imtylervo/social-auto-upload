# Zhihu automation

## Entry points and responsibilities

`sau_commands/zhihu.py` declares the CLI. In this directory `session.py`, `article.py`, `video.py`, `schedule.py` and `verification.py` handle the session, articles, videos, scheduling and the original-post lookup. Usage is described in `skills/zhihu-upload/SKILL.md`.

The session is `cookies/zhihu_<alias>.json` and the account binding is the adjacent `.identity.json`. `session.py::PROFILE_IMAGE` reads the nickname and avatar path from the current-user entry in the page header. They are not a permanent user ID: renaming the account or changing the avatar makes the binding mismatch. Do not treat a login timeout or a network error as an expired session.

## Articles

`utils.article_render.load_article` parses HTML/Markdown/TXT. `article.py::fill_article_form` imports the body through an HTML paste and image position markers; `check_article_body` checks the full text, the interleaved image order, formatting and links. If a non-empty draft is restored, it stops and does not overwrite it.

- Title: `textarea[placeholder="请输入标题（最多 100 个字）"]` ("enter a title, at most 100 characters"), located by the editor's own hint text.
- Body: `div[contenteditable="true"][role="textbox"]`, distinct from the title textarea.
- PNG goes through the clipboard; other formats go through the image input, which still needs verification on the real page. The image toolbar button first opens the asset panel, so it cannot be used directly as a file picker.
- DraftJS bold may be a styled span, and links may carry zero-width characters; checks read them by their rendered meaning.

Success must be a real `/p/<id>`; a `/edit` draft URL does not count as published. After publishing, share and benefits prompts may appear; nothing is shared or enabled automatically.

## Videos

`video.py::main` runs in order: file checks, account check, upload, menu reading, form check, submission and reading the detail link.

```python
video_input = page.locator("input.VideoUploadButton-fileInput[type=file]")
field = page.locator(".VideoUploadForm-item").filter(
    has=page.get_by_text("所属领域", exact=True),
)
control = field.get_by_role("combobox")
```

The class of the file input comes from the upload home page. Business row labels scope the field (category), declaration and originality switch, excluding other dropdowns and checkboxes. The field list is the `role=option` items in `.VideoUploadForm-selectList:visible`, with the 选择领域 (choose a field) placeholder filtered out. The declaration popup is `.VideoUploadForm-videoTypeModal:visible`, its options are `.VideoUploadForm-videoTypeModalOption[role=button]`, and the choice is confirmed after selecting.

The full field and declaration texts are kept in `constants.py` for the CLI choices; at submission they are still checked against the live menu. When the menu gains or renames entries, update the constants. The topic toolbar button currently has no accessible name, so automatic topic selection is not wired in and there is no working `--topics` option.

The video size must be strictly greater than 102400 bytes. The page clears the input after handling change, so `files=0` does not prove no file was chosen; the upload state is judged from 上传成功 (upload succeeded), the failure message and the actual form.

The current entry shows 发布成功 (published) on the same page, and clicking 查看详情 (view details) opens `/pin/<id>` separately. `video.py` first records that the platform confirmed publishing, then reads the detail link; a failure to read the link must not fall back to unpublished or trigger a new upload. `verification.py` accepts article, pin video and old video detail paths.

## Verification limits

In the original logged-in browser, both articles and videos have been really published and their detail pages checked. The full Python CLI chain, non-PNG images and acceptance of scheduling still need separate verification; local tests do not replace evidence from live submissions. Investigation assets, screenshots and account results are kept in the ignored directory `.local/` and are not part of the public usage docs.

`--prepare-only` and the candidate lookup may save a draft automatically. When the result is unknown, look up the original post first; automatic republishing is forbidden. Scheduling is an experimental path: it may report scheduled success only after the platform's actual schedule has been checked.
