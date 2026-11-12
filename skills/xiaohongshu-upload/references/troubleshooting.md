# Troubleshooting

## `sau` command not found

Try the following:

```powershell
.\.venv\Scripts\Activate.ps1
sau xiaohongshu --help
```

```powershell
.\.venv\Scripts\sau.exe xiaohongshu --help
```

```bash
uv run sau xiaohongshu --help
```

If the project is not installed in the current environment yet:

```bash
uv pip install -e .
```

## Cookie invalid or expired

Check the cookie state first:

```bash
sau xiaohongshu check --account <account>
```

If it is invalid, log in again:

```bash
sau xiaohongshu login --account <account>
```

## Handling the QR code in headless login

If the user cannot use the terminal QR code output:

- Find the temporary QR code image printed by the CLI
- The agent should not just reply with the image path
- The agent should show or send the local QR code image to the user to scan

If the terminal QR code does not display correctly, use the saved image path instead of repeatedly trying random terminal settings.

## Missing upload arguments

### Video upload

At minimum:

- `--account`
- `--file`
- `--title`

### Image post upload

At minimum:

- `--account`
- `--images`
- `--title`

`--note` is currently the optional image post body.

## Scheduled publishing

Use this time format:

```text
YYYY-MM-DD HH:MM
```

If you do not need scheduled publishing, remove `--schedule` to publish immediately.
