from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from html import escape
import subprocess
from urllib.error import URLError

try:
    from telethon import TelegramClient
    from telethon.errors import AuthTokenExpiredError, SessionPasswordNeededError
    from telethon.sessions import StringSession
except Exception as exc:  # pragma: no cover - import-time guard for local setup
    print("Telethon is not installed. Install project dependencies first.", file=sys.stderr)
    raise SystemExit(1) from exc


def load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_key = key.strip()
        normalized_value = value.strip()
        os.environ.setdefault(normalized_key, normalized_value)
        os.environ.setdefault(normalized_key.upper(), normalized_value)


def save_session_to_env(session_string: str) -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    updated = False
    new_lines: list[str] = []
    for line in lines:
        if line.strip().startswith("telegram_session_string="):
            new_lines.append(f"telegram_session_string={session_string}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f"telegram_session_string={session_string}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def save_session_backup(session_string: str) -> Path:
    backup_path = Path("/tmp/marshallbot_telegram_session.txt")
    backup_path.write_text(session_string + "\n", encoding="utf-8")
    return backup_path


def write_qr_login_page(url: str) -> Path:
    page_path = Path("/tmp/marshallbot_telegram_qr_login.html")
    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>MarshallBot Telegram Login QR</title>
    <style>
      body {{
        margin: 0;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
        background: #08111f;
        color: #e6eefb;
        display: grid;
        place-items: center;
        min-height: 100vh;
      }}
      .card {{
        width: min(92vw, 560px);
        padding: 24px;
        border-radius: 20px;
        background: #0d1a2d;
        border: 1px solid rgba(255,255,255,.08);
        box-shadow: 0 20px 60px rgba(0,0,0,.35);
      }}
      h1 {{ margin: 0 0 12px; font-size: 24px; }}
      p {{ color: #8ba6c7; line-height: 1.5; }}
      .qr {{
        background: #fff;
        display: inline-block;
        padding: 12px;
        border-radius: 16px;
        margin: 16px 0;
      }}
      .url {{
        word-break: break-all;
        background: rgba(255,255,255,.04);
        padding: 12px;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,.08);
        font-size: 13px;
      }}
      .hint {{
        font-size: 13px;
        color: #8bf0b6;
      }}
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
  </head>
  <body>
    <div class="card">
      <h1>Scan to log in to Telegram</h1>
      <p>Open Telegram on your phone, go to Settings, and scan this QR code. Keep this page open until it completes.</p>
      <div class="qr" id="qr"></div>
      <div class="hint">If QR rendering fails, use the raw URL below.</div>
      <div class="url">{escape(url)}</div>
    </div>
    <script>
      new QRCode(document.getElementById("qr"), {{
        text: {url!r},
        width: 280,
        height: 280,
        correctLevel: QRCode.CorrectLevel.M,
      }});
    </script>
  </body>
</html>
"""
    page_path.write_text(html, encoding="utf-8")
    return page_path


def try_open_page(path: Path) -> None:
    try:
        subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


async def main() -> None:
    load_env_file()
    api_id = os.environ.get("TELEGRAM_API_ID") or os.environ.get("telegram_api_id")
    api_hash = os.environ.get("TELEGRAM_API_HASH") or os.environ.get("telegram_api_hash")

    if not api_id or not api_hash:
        print("Set telegram_api_id and telegram_api_hash in .env first.", file=sys.stderr)
        raise SystemExit(1)

    print("A Telegram login code will be sent to your Telegram app/phone.")
    phone = input("Phone number (international format, e.g. +234...): ").strip()

    try:
        async with TelegramClient(StringSession(), int(api_id), api_hash) as client:
            try:
                await client.send_code_request(phone)
                code = input("Telegram login code: ").strip()
                try:
                    await client.sign_in(phone=phone, code=code)
                except Exception as exc:  # pragma: no cover - depends on user account state
                    if "password" in str(exc).lower():
                        password = input("2FA password: ").strip()
                        await client.sign_in(password=password)
                    else:
                        raise
            except Exception as exc:
                if "SendCodeUnavailableError" not in exc.__class__.__name__ and "SendCodeUnavailableError" not in str(type(exc)):
                    raise

                print(
                    "Telegram blocked login-code delivery for this number.\n"
                    "Switching to QR login, which avoids the resend limit.",
                    file=sys.stderr,
                )
                qr_login = await client.qr_login()
                while True:
                    qr_path = write_qr_login_page(qr_login.url)
                    try_open_page(qr_path)
                    print(f"Scan the QR code in your Telegram app. A helper page was written to: {qr_path}")
                    try:
                        await qr_login.wait()
                    except AuthTokenExpiredError:
                        print("QR token expired. Refreshing the QR code now...", file=sys.stderr)
                        await qr_login.recreate()
                        continue
                    except SessionPasswordNeededError:
                        password = input("2FA password: ").strip()
                        await client.sign_in(password=password)
                    except Exception as qr_exc:
                        if await client.is_user_authorized():
                            break
                        print(
                            f"QR login still pending after error ({qr_exc.__class__.__name__}). Refreshing...",
                            file=sys.stderr,
                        )
                        await asyncio.sleep(2)
                        try:
                            await qr_login.recreate()
                        except Exception:
                            pass
                        continue

                    if await client.is_user_authorized():
                        break

            session_string = client.session.save()
            print("\nSave this as telegram_session_string:\n")
            print(session_string)
            backup_path = save_session_backup(session_string)
            save_session_to_env(session_string)
            print(f"\nAlso saved a backup copy to: {backup_path}")
            print("\nSaved telegram_session_string to .env")
    except (URLError, OSError) as exc:
        print(
            "Cannot connect to Telegram from this machine.\n"
            "Check internet/DNS/firewall/VPN, then try again.\n"
            f"Error: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
