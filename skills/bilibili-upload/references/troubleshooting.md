# Bilibili common problems

## 1. The first run is slow

This is normal.

The usual reason is that the program is downloading `biliup` automatically.

## 2. The automatic download fails

Check first:

- Whether the current network can reach GitHub
- Whether GitHub Releases is reachable
- Whether the local directory is writable
- If the network in mainland China is slow, you can first use `https://gh-proxy.com/` or `https://gh-proxy.org/` to help reach the release address for troubleshooting
- Example:
  - `https://gh-proxy.org/https://github.com/biliup/biliup/releases/download/v1.1.29/biliupR-v1.1.29-aarch64-linux.tar.xz`

## 3. `check` returns `invalid`

Common causes:

- The account file does not exist
- The login information has expired
- `biliup renew` failed

Suggestion:

```bash
sau bilibili login --account <account>
```

## 4. Login reports `not a terminal`

Common causes:

- You triggered `sau bilibili login` in a non-interactive environment
- For example an agent's command runner, a piped environment, or a process whose standard output is taken over

Suggestion:

- Have the user run it in a real local terminal instead:

```bash
sau bilibili login --account <account>
```

- If the QR code in the terminal is displayed incompletely, open `qrcode.png` in the current directory and scan it

## 5. The upload fails

Check first:

- Whether `--tid` is correct
- Whether the video file really exists
- Whether the title, description and tags meet the platform's requirements
- Whether the current login information is still valid

## 6. Behavior changes after an upstream update

The current Bilibili integration automatically follows the latest upstream `biliup` release.

If the upstream command behavior changes, it may affect this project's Bilibili CLI.

When troubleshooting, also confirm:

- The `biliup` version currently downloaded
- Whether the upstream release has changed recently
