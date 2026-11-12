# Browser Platform CLI Unification and Xiaohongshu Skill Design

Date: 2026-03-25

## Summary

This design unifies the main-line interface of three browser-automation platforms:

- Douyin
- Kuaishou
- Xiaohongshu

The goal is not to rewrite the uploaders or to add another complex framework layer. It is to bring the CLI, skills, docs and examples, which exist today but are inconsistent, into one unified contract.

This design solves two practical problems at once:

1. Xiaohongshu already has a working browser uploader, but it is not connected to the `sau` CLI and has no skill.
2. The current Douyin and Kuaishou CLI contracts still carry legacy fields. For example, videos have no separate `--desc`, and the naming of the image post body is mixed up with the video description semantics. This makes it hard for the three browser platforms to form one stable, unified main-line interface.

After this unification, the external entries are fixed as:

- `sau douyin ...`
- `sau kuaishou ...`
- `sau xiaohongshu ...`

Video and image post uploads on all three browser platforms follow one unified main-line option model:

- Video: `title + desc + tags`
- Image post: `title + note + tags`

## Goals

- Add the main-line CLI for Xiaohongshu:
  - `login`
  - `check`
  - `upload-video`
  - `upload-note`
- Unify the CLI upload option model of the three browser platforms: Douyin, Kuaishou and Xiaohongshu
- Add the Xiaohongshu skill, example scripts, README, CLI docs and install/update docs
- Fix the missing `desc` capability in the existing Douyin and Kuaishou CLI contracts
- Keep the main logic of the existing uploaders mostly unchanged, and avoid over-wrapping

## Non-goals

- This change does not restructure the uploader architecture
- This change does not touch the old Web path
- This change does not alter the Bilibili upload contract
- This change does not add browser integration tests
- This change does not keep a public `--note` main contract

## Current project foundation

### Existing capabilities

- Douyin and Kuaishou are already connected to `sau_cli.py`
- Bilibili is already connected to the CLI and has a skill
- Xiaohongshu already has:
  - Login
  - Cookie validation
  - Video upload
  - Image post upload
  - Scheduled publishing
- The Xiaohongshu uploader already supports internally:
  - Video: `title + desc + tags`
  - Image post: `title + desc + tags`
  - `desc` in an image post is optional

### Current inconsistencies

- Douyin video CLI: `--title`, `--tags`, no `--desc`
- Kuaishou video CLI: `--title`, `--tags`, no `--desc`
- Douyin image post CLI: `--note`, `--tags`
- Kuaishou image post CLI: `--note`, `--tags`
- Xiaohongshu has no CLI/skill interface yet

In other words, the main-line capabilities of the three browser platforms are not unified today. In particular:

- The video description is not exposed uniformly as `desc`
- It is not settled whether the image post body should keep the `note` semantics

## Unified CLI design

### Supported platforms

- `douyin`
- `kuaishou`
- `xiaohongshu`

### Supported actions

Every platform supports:

- `login`
- `check`
- `upload-video`
- `upload-note`

### Unified upload option model

#### Video upload

```bash
sau <platform> upload-video \
  --account <account_name> \
  --file <video-path> \
  --title "<title>" \
  [--desc "<description>"] \
  [--tags tag1,tag2] \
  [--schedule "YYYY-MM-DD HH:MM"] \
  [platform-specific options...]
```

Unified rules:

- `--title` required
- `--desc` optional
- `--tags` optional
- `--schedule` optional

Platform-specific options:

- Douyin:
  - `--thumbnail`
  - `--product-link`
  - `--product-title`
- Kuaishou:
  - `--thumbnail`
- Xiaohongshu:
  - `--thumbnail`

#### Image post upload

```bash
sau <platform> upload-note \
  --account <account_name> \
  --images <image-1> [image-2 ...] \
  --title "<title>" \
  [--note "<content>"] \
  [--tags tag1,tag2] \
  [--schedule "YYYY-MM-DD HH:MM"]
```

Unified rules:

- `--images` required
- `--title` required
- `--note` optional
- `--tags` optional
- `--schedule` optional

Explicit decisions:

- The main-line body of an image post is called `note`
- The main-line description of a video is called `desc`
- Docs, skills and examples use:
  - Video: `--title + --desc + --tags`
  - Image post: `--title + --note + --tags`

## Data model design

To keep the mapping between the CLI layer and the uploader layer clear, each platform keeps its own request dataclass, but the field names are unified.

### Video request object

Unified fields:

- `account_name`
- `video_file`
- `title`
- `description`
- `tags`
- `publish_date`
- `publish_strategy`
- `debug`
- `headless`

Platform-specific fields are kept:

- Douyin:
  - `thumbnail_file`
  - `product_link`
  - `product_title`
- Kuaishou:
  - `thumbnail_file`
- Xiaohongshu:
  - `thumbnail_file`

### Image post request object

Unified fields:

- `account_name`
- `image_files`
- `title`
- `note`
- `tags`
- `publish_date`
- `publish_strategy`
- `debug`
- `headless`

`note` is deliberately kept here, because it fits the image post body better and should not be forced to reuse the `description / desc` naming of videos.

## Mapping to the existing uploaders

### Douyin

- Video upload keeps reusing `DouYinVideo`
- Add the `desc` input mapping to Douyin video
- Image post upload now takes `title + note + tags` explicitly
- At the CLI layer, `note` is mapped to the Douyin image post body input area

### Kuaishou

- Video upload keeps reusing `KSVideo`
- Add the `desc` input mapping to Kuaishou video
- Image post upload now takes `title + note + tags` explicitly

### Xiaohongshu

- Login and validation connect directly to `xiaohongshu_setup` / `cookie_auth`
- Video upload reuses `XiaoHongShuVideo`
- Image post upload reuses `XiaoHongShuNote`
- Because the Xiaohongshu uploader already supports `title + desc + tags`, the CLI layer only needs to map `note` to the image post body consistently

## Compatibility and migration strategy

This change takes the approach of "unify directly, and do not keep the old vague public contract".

Concretely:

- `README.md`
- `docs/CLI.md`
- `docs/install.md`
- `docs/update.md`
- `skills/douyin-upload/...`
- `skills/kuaishou-upload/...`
- The new `skills/xiaohongshu-upload/...`

all switch to the new contract in the same round, to avoid:

- Some docs writing the image post body as `--note`
- Some docs writing the image post body as `--desc`

The cost is that old example commands stop working, but in return the main-line contract is fully unified:

- Video is always `desc`
- Image post is always `note`

## Skill design

New:

- `skills/xiaohongshu-upload/SKILL.md`
- `skills/xiaohongshu-upload/references/cli-contract.md`
- `skills/xiaohongshu-upload/references/runtime-requirements.md`
- `skills/xiaohongshu-upload/references/troubleshooting.md`

Also updated in step:

- `skills/douyin-upload/SKILL.md`
- `skills/douyin-upload/references/cli-contract.md`
- `skills/kuaishou-upload/SKILL.md`
- `skills/kuaishou-upload/references/cli-contract.md`

The skill principles stay the same:

- Prefer `sau`
- The agent should not read the uploader source first
- Look at troubleshooting only when the CLI fails
- Show the login QR code image directly to the user to scan

## Documentation design

Update at least:

- `README.md`
- `docs/CLI.md`
- `docs/install.md`
- `docs/update.md`

The unified wording:

- All three browser platforms are connected to the CLI
- All three browser platforms are connected to skills
- Unified fields for video upload:
  - `title`
  - `desc`
  - `tags`
- Unified fields for image post upload:
  - `title`
  - `note`
  - `tags`
- `account_name` is a user-defined account name. It is not fixed to `creator`
- One `account_name` maps to one account file, so multiple accounts can be isolated and run concurrently

## Example design

The examples keep two kinds of paths:

1. CLI main-line examples
2. Legacy direct-uploader examples

Xiaohongshu needs to be brought to the same level of main-line presentation as the other platforms:

- `examples/get_xiaohongshu_cookie.py`
- `examples/upload_video_to_xiaohongshu.py`
- If necessary, add a call example closer to the CLI contract

The README and docs must state clearly:

- Prefer `sau xiaohongshu ...`
- The legacy direct-uploader examples are only a debugging entry

## Error handling

### Option-level errors

Handled by the CLI parser:

- File does not exist
- Invalid time format
- Missing `--title`
- Missing `--images`

### Business-level errors

Handled by the uploaders and existing validation:

- Cookie does not exist
- Cookie has expired
- Upload failed
- Unexpected page structure

### QR code wording

All three browser platforms keep this statement:

- If the login flow generates a local QR code image, the agent should show or send the image to the user to scan, instead of only returning the path

## Test strategy

This change only does minimal but valuable CLI-level verification, with no browser integration tests.

Add at least these tests:

- The parser recognizes `xiaohongshu`
- The new contract parses correctly on the three platforms:
  - `upload-video --title --desc --tags`
  - `upload-note --images --title --note --tags`
- Dispatch converts the options into the matching request correctly
- The Xiaohongshu `login/check/upload-video/upload-note` branches are routed correctly

Keep the existing:

- `tests/test_xiaohongshu_uploader.py`

## Files affected

### Must change

- `sau_cli.py`
- `README.md`
- `docs/CLI.md`
- `docs/install.md`
- `docs/update.md`

### New

- The full set of files under `skills/xiaohongshu-upload/`
- The matching CLI unit test file

### Changed in step

- `skills/douyin-upload/...`
- `skills/kuaishou-upload/...`
- `examples/get_xiaohongshu_cookie.py`
- `examples/upload_video_to_xiaohongshu.py`

## Recommended implementation order

1. Change `sau_cli.py` and the request models first
2. Wire up the Xiaohongshu CLI routing
3. Add the `desc` / new image post field mapping for Douyin and Kuaishou
4. Add the CLI unit tests
5. Add the Xiaohongshu skill
6. Update the Douyin and Kuaishou skill contracts
7. Update the README / CLI / install / update docs
8. Update the examples

## Final conclusions

- The three browser platforms are unified on one set of CLI actions:
  - `login`
  - `check`
  - `upload-video`
  - `upload-note`
- The three browser platforms are unified on one main-line metadata model:
  - Video: `title + desc + tags`
  - Image post: `title + note + tags`
- Xiaohongshu gets its CLI and skill
- Douyin and Kuaishou get the `desc` capability, and the image post body field is unified as `note`
- The implementation stays lightweight, with no over-wrapping
