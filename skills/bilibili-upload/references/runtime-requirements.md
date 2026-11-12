# Runtime requirements

This skill assumes the current environment already has:

- `social-auto-upload` installed
- `sau` can be called, or at least `python sau_cli.py` can be run
- On the first run, the machine can go online and reach GitHub Releases

## Key points

The user does not need to install `biliup` themselves.

When you run `sau bilibili ...`:

- If `biliup` is not present locally, the program downloads it automatically
- If the upstream GitHub Release has an update, the program updates it automatically before continuing

## Recommended ways to call it

### `sau` is already on PATH

```bash
sau bilibili --help
```

### Call it directly from the repository

PowerShell:

```powershell
.\.venv\Scripts\python.exe sau_cli.py bilibili --help
```

bash / zsh:

```bash
python sau_cli.py bilibili --help
```

## Notes for the first run

- The first run may be slower than on other platforms, because `biliup` is prepared automatically
- If the network cannot reach GitHub Releases, Bilibili commands fail
- Once `biliup` is ready locally, later commands reuse it directly
- `sau bilibili login --account <name>` must be run by the user in a real local terminal
- If the terminal QR code is displayed incompletely, you can usually open `qrcode.png` in the current directory and scan it
- If GitHub Releases is slow to reach from mainland China, you can first use `https://gh-proxy.com/` or `https://gh-proxy.org/` to help reach the release address for troubleshooting
- Example:
  - `https://gh-proxy.org/https://github.com/biliup/biliup/releases/download/v1.1.29/biliupR-v1.1.29-aarch64-linux.tar.xz`
