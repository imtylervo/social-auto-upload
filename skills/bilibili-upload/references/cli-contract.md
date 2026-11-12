# Bilibili CLI contract

This skill assumes that `sau` is installed and callable in the current environment.

## Commands

### Login

```bash
sau bilibili login --account <account>
```

- Required arguments:
  - `--account`
- Purpose:
  - Prepares `biliup` automatically
  - Triggers the Bilibili login flow
- About accounts:
  - `--account` takes a user-defined `account_name`; it does not have to be `creator`
  - One `account_name` corresponds to one account file, which can be used to isolate multiple accounts and run tasks concurrently
- About how to log in:
  - This command should be run by the user in a real local terminal
  - If the terminal QR code is displayed incompletely, open `qrcode.png` in the current directory and scan it
  - The agent should not force this command to run in a non-interactive environment

### Check the account

```bash
sau bilibili check --account <account>
```

- Required arguments:
  - `--account`
- Expected output:
  - `valid`
  - `invalid`

### Upload a video

```bash
sau bilibili upload-video \
  --account <account> \
  --file <video-path> \
  --title "<title>" \
  --desc "<desc>" \
  --tid <category-id> \
  [--tags tag1,tag2] \
  [--schedule "YYYY-MM-DD HH:MM"]
```

- Required arguments:
  - `--account`
  - `--file`
  - `--title`
  - `--desc`
  - `--tid`
- Optional arguments:
  - `--tags`
  - `--schedule`

## Additional notes

- `--tid` is required in this first version
- `--tags` is comma-separated
- `--schedule` uses the common `sau` time format
- The program prepares and updates `biliup` automatically
