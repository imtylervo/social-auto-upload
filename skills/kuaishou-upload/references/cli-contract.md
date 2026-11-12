# Kuaishou CLI contract

This skill assumes that `sau` is installed and callable in the current environment.

## Commands

### Login

```bash
sau kuaishou login --account <account>
```

- Required arguments:
  - `--account`
- Purpose:
  - Start the Kuaishou login flow and create or refresh the cookie file for the given account
  - If a local QR code image is generated during login, the agent should show or send the image to the user to scan, rather than only returning the path
- About accounts:
  - `--account` takes a user-defined `account_name`; it does not have to be `creator`
  - One `account_name` corresponds to one account file, which can be used to isolate multiple accounts and run tasks concurrently

### Check the cookie

```bash
sau kuaishou check --account <account>
```

- Required arguments:
  - `--account`
- Expected output:
  - `valid`: the cookie is usable
  - `invalid`: the cookie is missing or has expired

### Upload a video

```bash
sau kuaishou upload-video \
  --account <account> \
  --file <video-path> \
  --title "<title>" \
  [--desc "<description>"] \
  [--tags tag1,tag2] \
  [--schedule "YYYY-MM-DD HH:MM"] \
  [--thumbnail <image-path>] \
  [--debug] \
  [--headless | --headed]
```

- Required arguments:
  - `--account`
  - `--file`
  - `--title`
- Optional arguments:
  - `--desc`
  - `--tags`
  - `--schedule`
  - `--thumbnail`
  - `--debug`
  - `--headless`
  - `--headed`

### Upload an image post

```bash
sau kuaishou upload-note \
  --account <account> \
  --images <image-1> [image-2 ...] \
  --title "<title>" \
  [--note "<content>"] \
  [--tags tag1,tag2] \
  [--schedule "YYYY-MM-DD HH:MM"] \
  [--debug] \
  [--headless | --headed]
```

- Required arguments:
  - `--account`
  - `--images`
  - `--title`
- Optional arguments:
  - `--note`
  - `--tags`
  - `--schedule`
  - `--debug`
  - `--headless`
  - `--headed`

## Publishing policy

- Without `--schedule`, the CLI publishes immediately
- With `--schedule`, the CLI switches to scheduled publishing automatically
- The time format is:

```text
YYYY-MM-DD HH:MM
```

## Additional notes

- `upload-video` accepts only one video file per command
- `upload-note` accepts multiple images per command
- The video description always uses `--desc`
- The image post body always uses `--note`
- `upload-note` currently requires multiple real image files, not the same path repeated several times
