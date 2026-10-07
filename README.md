# Raspberry Pi Telegram Chat Bot

A lightweight, asynchronous Telegram bot built with `python-telegram-bot` (v20+) and designed specifically for resource-constrained edge devices (Raspberry Pi 3B+).

---

## 1. Hardware and Operational Constraints

This application is engineered to operate strictly within the physical limits of an edge device:
- **Host Device:** Raspberry Pi 3B+ (ARMv7 / Cortex-A53, 1 GB RAM total, ~664 MB free).
- **RAM Budget:** Strict limit of 150 MB process memory (production daemon runs at ~53 MB resident memory).
- **Zero Swap:** Swapping to MicroSD storage causes flash degradation and CPU thrashing; zero swap usage is maintained.
- **Network Architecture:** Operates behind restricted firewalls with client isolation. Uses Telegram Long-Polling exclusively (`Application.run_polling()`). No open ports, webhooks, or reverse proxies.
- **Persistence:** Local SQLite database (`bot_memory.db`) with Write-Ahead Logging (WAL mode) for minimal disk I/O and zero external database overhead.

---

## 2. Configuration (.env)

Create a `.env` file in the project root based on `.env.example`:

```ini
# Telegram Bot Credentials
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ADMIN_CHAT_ID=your_telegram_chat_id_here

# LLM Credentials
GEMINI_TOKEN_KEY=your_gemini_api_key_here

# Application Configuration
LOG_LEVEL=INFO
LOG_TO_CONSOLE=true
LOG_TO_FILE=true
LOG_FILE_PATH=bot.log
DATABASE_PATH=bot_memory.db
```

### Environment Separation
- **Local Development (PC):** Set `TELEGRAM_BOT_TOKEN` to your test bot token. Runs on demand.
- **Production Server (Pi):** Set `TELEGRAM_BOT_TOKEN` to your production bot token. Runs 24/7 under systemd.

---

## 3. Local Development Workflow (Windows PC)

### 3.1. Setup Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3.2. Run Offline Unit Tests
All tests run completely offline with mocked Telegram and API dependencies:
```powershell
pytest
```

### 3.3. Run the Development Bot
Start the bot locally to test features and commands in real time:
```powershell
python main.py
```

---

## 4. Production Deployment (Raspberry Pi)

### 4.1. Systemd Service
The production bot runs as a managed systemd background service defined in `systemd/telegram-bot.service`.

- **Check Service Status:**
  ```bash
  systemctl status telegram-bot.service
  ```
- **Restart Service:**
  ```bash
  sudo systemctl restart telegram-bot.service
  ```
- **Inspect Live Logs:**
  ```bash
  journalctl -u telegram-bot.service -f
  ```

### 4.2. Pull-Based CI/CD Script (`deploy.sh`)
Deployments are governed by `deploy.sh`. The script executes this sequence:
1. Navigates to `~/pi-telegram-chat-bot`.
2. Pulls latest changes from `origin/main`.
3. Activates the Python virtual environment (`venv`).
4. Installs updated dependencies non-interactively (`pip install --no-input -r requirements.txt`).
5. Applies SQLite database migrations (`core.db.init_db`).
6. Executes `pytest` test suite as an automated gatekeeper.
7. Restarts `telegram-bot.service` if and only if all tests pass.

If any command or test fails, the script halts immediately via a bash `ERR` trap and keeps the previous stable service running.

### 4.3. Immediate Manual Deployment
To deploy pushed changes to the Pi immediately:

- **From an active SSH session on the Pi:**
  ```bash
  bash ~/pi-telegram-chat-bot/deploy.sh
  ```
- **From Windows PowerShell via SSH:**
  ```powershell
  ssh admin@100.66.255.69 "bash ~/pi-telegram-chat-bot/deploy.sh"
  ```

### 4.4. Automated Scheduled Deployment (Cron)
A nightly cron job triggers `deploy.sh` at 03:00 CEST:
```bash
0 3 * * * /bin/bash /home/admin/pi-telegram-chat-bot/deploy.sh >> /home/admin/deploy.log 2>&1
```
Check recent automated deployment logs:
```bash
tail -n 30 /home/admin/deploy.log
```