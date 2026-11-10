#!/usr/bin/env python3
"""Hermes-mini: lightweight 24/7 Telegram bot for the owner.
- DM co-pilot drafts (client DM paste -> Hinglish reply + NEXT MOVE)
- Morning checklist auto 09:30 IST
- /health HTTP endpoint for external keep-alive pings
Deps: requests only.
"""
import os
import json
import time
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED = int(os.environ.get("TELEGRAM_ALLOWED_USERS", "8586289761"))
OR_KEY = os.environ.get("OPENROUTER_API_KEY", "")
MODEL = os.environ.get("LLM_MODEL", "nvidia/nemotron-3.5-super-vl:free")
API = "https://api.telegram.org/bot" + TOKEN
IST = timedelta(hours=5, minutes=30)

SYSTEM = (
    "Tu 'Hermes helper' hai. Boss (Anurag) ke chhote-business clients ke liye DM replies likhta hai. "
    "RULES: reply Hinglish me, warm but professional, 2-6 lines, max 2 emoji. "
    "PRICING locked: Website 2999 (basic) / 4999 (premium photos+gallery); 8-reel pack 1999; "
    "maintenance 299/month; FREE demo draft offer bait; minimum discount 2500; kaam shuru hone se "
    "pehle 50% advance (1500) lena zaruri. Demo links: salon https://mehrakalpana519-pixel.github.io/demo-salon/ "
    "gym https://mehrakalpana519-pixel.github.io/demo-gym/ coach https://mehrakalpana519-pixel.github.io/demo-coach/ "
    "Cold DM intro: 'Namaste [naam]! [shop ka naam] ka website online nahi dikh rahi. Main chhote businesses ke "
    "liye 2999 me 1-din website banata hun - WhatsApp button seedha customers ko connect karega. FREE demo draft "
    "bhejun, pasand aaye to hi bolo?' "
    "Har draft ke end me ek line 'NEXT MOVE:' do (demo bhejo / advance book karo / call fix karo / 2 din me follow-up). "
    "Client naraz ya silent ho to emotional na ho; lukewarm safe reply do."
)

CHECKLIST = (
    "\U0001F305 MORNING HUNT CHECKLIST\n"
    "1) 20-30 naye targets ko DM (salon, gym, coach, boutiques) - 15 min\n"
    "2) Sabse warm client ko FREE demo link bhejo:\n"
    "salon: mehrakalpana519-pixel.github.io/demo-salon\n"
    "gym: mehrakalpana519-pixel.github.io/demo-gym\n"
    "coach: mehrakalpana519-pixel.github.io/demo-coach\n"
    "3) 1 follow-up: 2 din purane lead pe wapas ping\n"
    "RULE: Advance 1500 ke baad hi kaam shuru. Aaj ka target: 1 demo bhejo."
)


def tg(method, **kwargs):
    try:
        r = requests.post(API + "/" + method, json=kwargs, timeout=30)
        return r.json()
    except Exception as e:  # noqa: BLE001
        print("tg error", method, e)
        return None


def send_text(chat_id, text):
    for i in range(0, len(text), 3800):
        tg("sendMessage", chat_id=chat_id, text=text[i : i + 3800])


def llm(client_text, kind="dm"):
    if not OR_KEY:
        return "OPENROUTER key missing - main abhi AI reply nahi de sakta."
    if kind == "dm":
        user = ("Client ne ye DM bheja hai. Best Hinglish reply draft karo "
                "(2-6 lines, max 2 emoji) aur end me NEXT MOVE line:\n\n" + client_text)
    else:
        user = client_text
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "max_tokens": 700,
    }
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=body,
            headers={"Authorization": "Bearer " + OR_KEY},
            timeout=90,
        )
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:  # noqa: BLE001
        print("llm error", e)
        return "Network thoda busy tha, ye message dobara bhejo."


class Health(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"hermes-mini ok")

    def log_message(self, *args):  # keep logs tiny
        return


def health_server():
    port = int(os.environ.get("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), Health).serve_forever()


def ist_now():
    return datetime.utcnow() + IST


def daily_checklist():
    last = ""
    while True:
        now = ist_now()
        today = now.strftime("%Y-%m-%d")
        if now.hour == 9 and now.minute >= 30 and last != today:
            last = today
            send_text(ALLOWED, CHECKLIST)
        nxt = datetime(now.year, now.month, now.day, 9, 31) + timedelta(days=1)
        time.sleep(max(60, (nxt - now).total_seconds() * 0.4))


def handle(message):
    chat_id = str(message["chat"]["id"])
    if int(chat_id) != ALLOWED:
        return
    text = (message.get("text") or "").strip()
    if not text:
        return
    low = text.lower()
    if low.startswith("/start"):
        send_text(chat_id, (
            "\U0001F916 Hermes-mini ONLINE - 24/7!\n\n"
            "\u2022 Client ka message paste karo \u2192 main Hinglish reply draft dunga (pricing locked)\n"
            "\u2022 /checklist \u2192 abhi ki checklist\n"
            "\u2022 Baaki koi bhi baat \u2192 main jawab dunga\n\n"
            "Advance rule: \u20B91,500 pehle, phir hi kaam shuru."
        ))
        return
    if low.startswith("/checklist"):
        send_text(chat_id, CHECKLIST)
        return
    is_client_dm = len(text) > 60 or any(w in low for w in ["dm", "price", "kitna", "demo", "advance", "rate"])
    reply = llm(text, "dm" if is_client_dm else "chat")
    send_text(chat_id, reply)


def main():
    threading.Thread(target=health_server, daemon=True).start()
    threading.Thread(target=daily_checklist, daemon=True).start()
    send_text(ALLOWED, "\U0001F7E2 Hermes-mini DEPLOYED - bot ab 24/7 online hai!")
    offset = 0
    while True:
        try:
            r = requests.get(
                API + "/getUpdates",
                params={"offset": offset + 1, "timeout": 50, "allowed_updates": json.dumps(["message"])},
                timeout=60,
            )
            data = r.json()
            for upd in data.get("result", []):
                offset = max(offset, upd["update_id"])
                msg = upd.get("message")
                if msg:
                    try:
                        handle(msg)
                    except Exception as e:  # noqa: BLE001
                        print("handle error", e)
        except Exception as e:  # noqa: BLE001
            print("poll error", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
