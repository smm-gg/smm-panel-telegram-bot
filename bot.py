"""SMM panel Telegram bot: order and track SMM.GG services from Telegram.

Set SMMGG_API_KEY, TELEGRAM_BOT_TOKEN and ALLOWED_USER_IDS, then run: python bot.py
"""
import os
import time

import requests

SMM_API = "https://smm.gg/api/v2"
SMM_KEY = os.environ["SMMGG_API_KEY"]
TG_API = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}"
ALLOWED = {int(x) for x in os.environ.get("ALLOWED_USER_IDS", "").split(",") if x.strip()}

HELP = """SMM.GG bot

/balance - your balance
/services <search> - find services, e.g. /services instagram followers
/order <service_id> <link> <quantity> - place an order
/status <order_id> - order status
/refill <order_id> - request a refill"""


def smm(action, **fields):
    r = requests.post(SMM_API, data={"key": SMM_KEY, "action": action, **fields}, timeout=30)
    return r.json()


def tg(method, **params):
    return requests.post(f"{TG_API}/{method}", json=params, timeout=60).json()


def cmd_balance(_args):
    b = smm("balance")
    return b.get("error") or f"Balance: {b['balance']} {b['currency']}"


def cmd_services(args):
    words = [w.lower() for w in args]
    if not words:
        return "Usage: /services <search>"
    services = smm("services")
    if isinstance(services, dict):
        return services.get("error", "Could not load services.")
    found = [s for s in services if all(w in f"{s['name']} {s['category']}".lower() for w in words)]
    if not found:
        return "No services found."
    lines = [f"#{s['service']} {s['name']} - ${s['rate']}/1000 (min {s['min']}, max {s['max']})" for s in found[:15]]
    if len(found) > 15:
        lines.append(f"...and {len(found) - 15} more, narrow your search.")
    return "\n".join(lines)


def cmd_order(args):
    if len(args) != 3 or not args[0].isdigit() or not args[2].isdigit():
        return "Usage: /order <service_id> <link> <quantity>"
    r = smm("add", service=args[0], link=args[1], quantity=args[2])
    return r.get("error") or f"Order placed: #{r['order']}"


def cmd_status(args):
    if len(args) != 1:
        return "Usage: /status <order_id>"
    r = smm("status", order=args[0])
    if "error" in r:
        return r["error"]
    return f"#{args[0]}: {r['status']}\nStart count: {r['start_count']}\nRemains: {r['remains']}\nCharge: {r['charge']} {r['currency']}"


def cmd_refill(args):
    if len(args) != 1:
        return "Usage: /refill <order_id>"
    r = smm("refill", order=args[0])
    return r.get("error") or f"Refill requested: #{r['refill']}"


COMMANDS = {"/balance": cmd_balance, "/services": cmd_services, "/order": cmd_order,
            "/status": cmd_status, "/refill": cmd_refill}


def handle(text):
    parts = text.split()
    cmd = parts[0].split("@")[0].lower() if parts else ""
    fn = COMMANDS.get(cmd)
    if not fn:
        return HELP
    try:
        return fn(parts[1:])
    except requests.RequestException:
        return "SMM.GG is not reachable right now, try again in a minute."


def main():
    if not ALLOWED:
        raise SystemExit("Set ALLOWED_USER_IDS so strangers can't spend your balance.")
    offset = 0
    while True:
        try:
            updates = tg("getUpdates", offset=offset, timeout=50).get("result", [])
        except requests.RequestException:
            time.sleep(5)
            continue
        for u in updates:
            offset = u["update_id"] + 1
            msg = u.get("message") or {}
            if not msg.get("text") or msg.get("from", {}).get("id") not in ALLOWED:
                continue
            tg("sendMessage", chat_id=msg["chat"]["id"], text=handle(msg["text"]),
               disable_web_page_preview=True)


if __name__ == "__main__":
    main()
