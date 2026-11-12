# Login
# Best run by the user in a real local terminal.
# If the terminal QR code is displayed incompletely, open qrcode.png in the current directory and scan it.
$account = "account_a"
# account_name is user-defined. One account_name maps to one account file.
# You can prepare multiple account names and run them in parallel.

sau bilibili login --account $account

# Check
sau bilibili check --account $account

# Upload a video
sau bilibili upload-video `
  --account $account `
  --file .\videos\demo.mp4 `
  --title "Bilibili CLI Demo" `
  --desc "Bilibili CLI Demo" `
  --tid 249 `
  --tags 足球,测试 `
  --schedule "2026-03-26 16:00"
