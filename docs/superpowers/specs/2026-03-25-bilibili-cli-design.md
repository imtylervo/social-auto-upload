# Bilibili CLI Design

Date: 2026-03-25

## Summary

This design adds `bilibili` under `sau`, with a user experience as close as possible to the existing `douyin` and `kuaishou`.

There are only two core constraints:

- Users do not need to install `biliup` themselves
- Externally, everything goes through `sau bilibili ...`

The program treats `biliup` as an internal runtime dependency:

- `sau bilibili ...` is the only public entry
- If `biliup` is not present locally, it is downloaded automatically
- Every run checks the latest GitHub Release version
- If an update is found, it is updated automatically first, and then the current command continues

This design is deliberately lightweight. It does not invent a new set of Bilibili upload semantics. It directly reuses the Bilibili upload model already in the repository.

## Goals

- Keep `sau bilibili ...` consistent in mental model with `sau douyin ...` and `sau kuaishou ...`
- Hide the installation details of `biliup` and lower the cost of use
- Reuse existing capabilities in the project, such as account files, `VideoZoneTypes` and scheduled publishing
- Avoid over-wrapping

## Non-goals

- The first version does not commit the `biliup` binary into the repository
- The first version does not maintain a local release manifest
- The first version does not support Bilibili image post publishing
- The first version does not redo the existing Bilibili upload domain model

## Current project foundation

The repository already has Bilibili upload capability:

- `uploader/bilibili_uploader/main.py` currently wraps `biliup.plugins.bili_webup` directly
- `examples/upload_video_to_bilibili.py` already uses the existing upload parameters
- `utils/constant.py` already defines the complete `VideoZoneTypes`

In other words, the Bilibili upload semantics in the project are already clear. The core is:

- `file`
- `title`
- `desc`
- `tid`
- `tags`
- `dtime`

So the first version of the CLI does not need to build a new model. It uses this one directly.

## User-facing CLI design

### Supported commands

- `sau bilibili login`
- `sau bilibili check`
- `sau bilibili upload-video`

### Command contracts

#### `sau bilibili login`

Purpose:

- Prepare `biliup` automatically
- Upgrade first if there is an update
- Then call `biliup` to complete login
- Save the account data according to the project's own account file rules

First-version behavior:

- If `biliup` is not present locally, download the latest release automatically
- If it is present locally but upstream has an update, upgrade automatically
- After the upgrade, continue with the login flow

#### `sau bilibili check`

Purpose:

- Prepare `biliup` automatically
- Check whether the current account is usable

First-version behavior:

- Decide by combining whether the local account file exists with whether `biliup` actually works
- The output style is consistent with the other platforms:
  - `valid`
  - `invalid`

#### `sau bilibili upload-video`

Purpose:

- Prepare `biliup` automatically
- Upload the video using the project's existing Bilibili upload parameters

First-version options:

- `--account` required
- `--file` required
- `--title` required
- `--desc` required
- `--tid` required
- `--tags` optional
- `--schedule` optional

Explicit decision:

- `tid` must be passed in the first version
- There is no default category, to avoid guessing and implicit errors

## Runtime dependency strategy

### Chosen approach

`biliup` is not committed into the repository, and users are not required to install it by hand.

`sau bilibili ...` handles it at runtime:

1. Look for an existing local `biliup`
2. Check the latest GitHub Release version
3. If it is missing or out of date, download the latest version automatically
4. Replace the local runtime copy
5. Continue with the current command

### Why this approach

- The repository stays smaller and cleaner
- Users do not need to find and download a release themselves
- Externally there is still one unified entry, `sau`
- There is no need for `git submodule`

### Accepted cost

This approach explicitly accepts a reality:

- Every run checks the upstream release
- If upstream changes its CLI behavior, this adaptation layer may be affected

So the answer here is not a heavy wrapper, but keeping the wrapper thin to reduce the cost of reactive maintenance.

## Storage and resolution

`biliup` should be stored in a local runtime cache directory, not in the source directory.

The cache directory only needs to be:

- Writable by the current user
- Reusable across commands
- Kept out of git

The resolver should:

- Detect the current operating system
- Pick the release asset for that platform
- Download and replace the executable
- Return the final executable path

## Lightweight wrapper boundaries

To avoid over-wrapping, the first version should be split into only 3 thin parts.

### 1. Resolver

Responsibilities:

- Decide whether `biliup` already exists locally
- Check the latest GitHub Release version
- Download or update the executable
- Return the final executable path

### 2. Runner

Responsibilities:

- Call the resolved `biliup`
- Collect the exit code, standard output and standard error
- Convert obvious process-level errors into friendly errors inside the project

### 3. The bilibili subcommand in `sau_cli.py`

Responsibilities:

- Parse the `sau bilibili ...` options
- Translate those options into the underlying run logic
- Keep the help text style consistent with the other platforms

The first version needs no more layers, and does not need another heavy unified framework.

## Mapping to existing project concepts

### Account files

Bilibili also keeps using the project's current account alias mechanism:

- The user passes `--account <name>`
- The program resolves it to the matching account file path

### Categories

`tid` stays a first-class option.

`VideoZoneTypes` stays and continues to serve:

- the example
- the docs
- possible helper tools later

### Scheduled publishing

`--schedule` keeps the same usage as the other `sau` platforms:

- Without it, publish immediately
- With it, publish on a schedule

How it maps to the underlying Bilibili execution logic is the adapter's job and is not exposed to the user.

## Error handling

First-version error handling stays direct, with no fancy wrapping:

- Download failure: tell the user clearly that the automatic download of `biliup` failed
- Update failure: tell the user clearly that preparing the latest release failed
- Login failure: keep the `biliup` login failure context
- Check failure: output `invalid`
- Upload failure: return a non-zero exit code and show a summary of the upstream error

The first version does not try to retranslate all `biliup` error text.

## Documentation impact

After the implementation is done, at least these places need to be updated:

- `README.md`
- `docs/CLI.md`
- The installation and update docs
- A matching Bilibili skill
- The Bilibili example script

The external message should be unified as:

- Users use `sau bilibili ...`
- `biliup` is prepared by the program automatically

## Test strategy

The first version needs to verify at least these paths:

- `sau bilibili login --account <name>`
- `sau bilibili check --account <name>`
- `sau bilibili upload-video ...`
- `biliup` is downloaded automatically when it is not present locally
- When an older version is present locally, it is upgraded first and then the command runs
- When the latest version is present locally, it is reused directly

Because login and upload involve a real external platform, it is acceptable for the first version to rely mainly on manual verification.

## Recommended implementation order

1. Add the `bilibili` subcommand in `sau_cli.py`
2. Add a minimal working `biliup` resolver
3. Add a minimal working `biliup` runner
4. Wire up `login / check / upload-video`
5. Fill in the docs, example and skill

## Final conclusions

- The external entry is fixed as `sau bilibili ...`
- The first version supports `login`, `check` and `upload-video`
- `tid` is required
- Users do not need to install `biliup` by hand
- Every run checks the GitHub Release
- When there is a new version, update automatically first, then continue
- The overall implementation stays lightweight, with no over-wrapping
