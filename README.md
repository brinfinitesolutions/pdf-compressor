# BR Infinite Compressor

Telegram product from [BR Infinite Solutions](https://www.brinfinitesolutions.com) for shrinking images and PDFs to a chosen size while keeping as much quality as possible.

`/start` opens the home screen. Tap **Compressor**, then send one image or PDF. The bot asks for a size cap, compresses **under that size**, then (for images) asks whether to return an **image** or a **PDF**.

## Setup

1. Talk to [@BotFather](https://t.me/BotFather), create a bot, copy the token.
2. Copy env and paste the token:

```bash
cp .env.example .env
```

1. Build and start:

```bash
make up
```

Set the bot profile picture to the logo and register `/start` in the command menu if it is not already there:

```bash
make init-bot
```

Follow logs with `make logs`. Stop with `make down`. Foreground run: `make run`.

The home logo is uploaded once, then reused from a Telegram `file_id` stored in `data/media.json` (mounted as a volume).

## Deploy (same droplet as digiBills)

Uses the SSH host alias `digibills-prod` and `/opt/pdf-compressor` on the server. Build `linux/amd64` on your laptop, copy the image, then start Compose without rebuilding on the droplet.

Once, as root on the droplet:

```bash
mkdir -p /opt/pdf-compressor/data && chown -R deployer:deployer /opt/pdf-compressor
```

Then create `/opt/pdf-compressor/.env` with `TELEGRAM_BOT_TOKEN` (this file is never rsynced). Optional: `UNLIMITED_CHAT_IDS=123,456` for chats that skip the daily cap of 5 files or 10 MB of input.
2. From this repo:

```bash
make deploy
```

Optional: `make deploy-init-bot` (profile photo and `/start` command), `make deploy-logs-f`, `make deploy-down`.

## Makefile


| Target          | What it does                                             |
| --------------- | -------------------------------------------------------- |
| `make build`    | `docker compose build`                                   |
| `make up`       | start in the background                                  |
| `make down`     | stop                                                     |
| `make logs`     | follow bot logs                                          |
| `make restart`  | rebuild and restart                                      |
| `make run`      | start in the foreground                                  |
| `make init-bot` | set the profile picture and register `/start` if missing |
| `make deploy` | build amd64 image, copy to `digibills-prod`, start the bot |
| `make deploy-logs-f` | follow production logs over SSH |
| `make deploy-init-bot` | run `init-bot` on the droplet |




## Usage

1. Send a photo, image document, or PDF.
2. Pick **200 KB**, **300 KB**, **500 KB**, **1 MB**, or **Custom KB** / **Custom MB**.
3. For custom sizes, send a number (for example `250` or `1.5`).
4. If you sent an image, choose **Send as image** or **Send as PDF**.
5. `/compress` starts the same flow as **Proceed Compressor**. `/cancel` drops the current file.

Results are sent as documents so Telegram does not recompress them.

Sending the file as a **document** (not a compressed Telegram photo) keeps more original quality.