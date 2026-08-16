#!/usr/bin/env python3
import os
import sys
import re
import json
import time
import datetime
import logging
import sqlite3
import queue
import threading
import socket
import ssl
import http.client
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

os.environ.setdefault("TZ", config.TZ)
if hasattr(time, "tzset"):
    time.tzset()

logging.basicConfig(filename=config.LOG, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

TOKEN = open(config.TOKEN_FILE).read().strip()

OFFSET = 0
UPDATE_QUEUE = queue.Queue()
WORKERS = 3


def db():
    conn = sqlite3.connect(config.DB, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


TR = {
    "es": {
        "start": ("<b>{name}</b>\n\n"
                  "Soy tu recordatorio personal. Llego puntual a la hora que me digas.\n\n"
                  "Cómo usarme:\n"
                  "• <code>/nuevo hoy 18:00 comprar pan</code>\n"
                  "• <code>/nuevo mañana 09:30 llamar a X</code>\n"
                  "• <code>/nuevo 20-08 12:00 cita médico</code>\n"
                  "• <code>/nuevo 2026-12-31 23:59 año nuevo</code>\n\n"
                  "Comandos: /lista · /hoy · /borrar &lt;id&gt; · /premium · /compartir\n\n"
                  "Free: {free} recordatorios activos. Premium: ilimitados + prioridad."),
        "nuevo_uso": "Uso: <code>/nuevo cuando texto</code>\n"
                     "Ej: <code>/nuevo mañana 09:30 llamar a X</code>",
        "nuevo_ok": "✅ Recordado: <b>{text}</b> · {when}",
        "limite": "⚠️ {msg}. Pásate a premium con /premium para ilimitados.",
        "lista_vacia": "No tienes recordatorios activos. Añade uno con /nuevo.",
        "lista_titulo": "<b>Tus recordatorios:</b>",
        "lista_pie": "\nBorra con /borrar &lt;id&gt;",
        "hoy_vacio": "Nada para hoy.",
        "hoy_titulo": "<b>Hoy:</b>",
        "borrar_uso": "Uso: <code>/borrar &lt;id&gt;</code> (mira /lista)",
        "borrar_invalido": "Ese no es un id válido.",
        "borrar_ok": "✅ Borrado.",
        "borrar_no": "No encontré ese recordatorio.",
        "premium_owner": "⭐ Eres el propietario: premium de por vida, gratis. ¡Disfruta!",
        "premium_ya": "⭐ Ya eres premium hasta el {until}. ¡Gracias!",
        "premium_info": ("⭐ <b>Premium</b>\n\n"
                         "• Recordatorios ilimitados\n"
                         "• Prioridad de entrega\n"
                         "• Apoyas el proyecto\n\n"
                         "Precio: <b>{price} ⭐</b> por {days} días.\n"
                         "Pulsa el botón de pago de abajo para pagar con Telegram Stars."),
        "no_auth": "No autorizado.",
        "test_factura": "Factura de prueba: <b>no te cobra nada</b> salvo que confirmes el pago.",
        "stats_titulo": "<b>Stats</b>\nUsuarios: {users} · Premium: {p} · Recordatorios activos: {r}\nReferidos: {ref} · Ingresos: {rev} ⭐",
        "ref_inviter": "🎁 ¡Un amigo se unió por tu enlace! Te regalo 1 mes premium (hasta el {until}).",
        "ref_welcome": "🎉 ¡Bienvenido! Has llegado por el enlace de un amigo. Disfruta de Memento.",
        "compartir": ("🎁 <b>Comparte y gana premium</b>\n\n"
                      "Cada amigo que se una con tu enlace te regala <b>{days} días premium</b> "
                      "(máx. {max} amigos).\n\n"
                      "Tu enlace:\n<code>{link}</code>"),
        "pago_ok": "🎉 ¡Pago recibido! Eres premium hasta el {until}.",
        "desconocido": "No conozco ese comando. Prueba /help",
    },
    "en": {
        "start": ("<b>{name}</b>\n\n"
                  "Your personal reminder, right inside Telegram. I show up on time.\n\n"
                  "How to use me:\n"
                  "• <code>/nuevo hoy 18:00 comprar pan</code>\n"
                  "• <code>/nuevo mañana 09:30 llamar a X</code>\n"
                  "• <code>/nuevo 20-08 12:00 cita médico</code>\n"
                  "• <code>/nuevo 2026-12-31 23:59 año nuevo</code>\n\n"
                   "Commands: /lista · /hoy · /borrar &lt;id&gt; · /premium · /share\n\n"
                  "Free: {free} active reminders. Premium: unlimited + priority."),
        "nuevo_uso": "Usage: <code>/nuevo when text</code>\n"
                     "Ex: <code>/nuevo mañana 09:30 llamar a X</code>",
        "nuevo_ok": "✅ Reminder set: <b>{text}</b> · {when}",
        "limite": "⚠️ {msg}. Go premium with /premium for unlimited reminders.",
        "lista_vacia": "No active reminders. Add one with /nuevo.",
        "lista_titulo": "<b>Your reminders:</b>",
        "lista_pie": "\nDelete with /borrar &lt;id&gt;",
        "hoy_vacio": "Nothing for today.",
        "hoy_titulo": "<b>Today:</b>",
        "borrar_uso": "Usage: <code>/borrar &lt;id&gt;</code> (see /lista)",
        "borrar_invalido": "That is not a valid id.",
        "borrar_ok": "✅ Deleted.",
        "borrar_no": "Reminder not found.",
        "premium_owner": "⭐ You are the owner: lifetime premium, free. Enjoy!",
        "premium_ya": "⭐ You are premium until {until}. Thank you!",
        "premium_info": ("⭐ <b>Premium</b>\n\n"
                         "• Unlimited reminders\n"
                         "• Delivery priority\n"
                         "• You support the project\n\n"
                         "Price: <b>{price} ⭐</b> per {days} days.\n"
                         "Tap the payment button below to pay with Telegram Stars."),
        "no_auth": "Not authorized.",
        "test_factura": "Test invoice: <b>you are not charged</b> unless you confirm the payment.",
        "stats_titulo": "<b>Stats</b>\nUsers: {users} · Premium: {p} · Active reminders: {r}\nReferrals: {ref} · Revenue: {rev} ⭐",
        "ref_inviter": "🎁 A friend joined through your link! Here is 1 month of premium (until {until}).",
        "ref_welcome": "🎉 Welcome! You came through a friend's link. Enjoy Memento.",
        "compartir": ("🎁 <b>Share and earn premium</b>\n\n"
                      "Each friend who joins with your link earns you <b>{days} days of premium</b> "
                      "(max {max} friends).\n\n"
                      "Your link:\n<code>{link}</code>"),
        "pago_ok": "🎉 Payment received! You are premium until {until}.",
        "desconocido": "I don't know that command. Try /help",
    },
}


def lang_of(u):
    if not u:
        return "es"
    return "es" if u["lang"] not in ("en",) else "en"


def T(u, key, **kw):
    lang = lang_of(u)
    return TR[lang].get(key, TR["es"][key]).format(**kw)


def init_db():
    conn = db()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, premium_until REAL, created_at REAL, lang TEXT DEFAULT 'es')""")
    conn.execute("""CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT,
        due_ts REAL, done INTEGER DEFAULT 0, created_at REAL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, stars INTEGER,
        payload TEXT, created_at REAL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT, inviter_id INTEGER, referred_id INTEGER,
        created_at REAL, UNIQUE(referred_id))""")
    try:
        conn.execute("ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'es'")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def api(method, data=None, timeout=60):
    body = json.dumps(data).encode() if data is not None else None
    conn = _open_conn(timeout)
    try:
        conn.request("POST", "/bot{}/{}".format(TOKEN, method), body=body,
                     headers={"Content-Type": "application/json", "Host": "api.telegram.org"})
        resp = conn.getresponse()
        return json.loads(resp.read().decode())
    except Exception:
        _IP_CACHE.clear()
        raise
    finally:
        conn.close()


_IP_CACHE = []
_IP_LAST = 0
_IP_LOCK = threading.Lock()
_IP_TTL = 600


def _resolve_ip():
    global _IP_CACHE, _IP_LAST
    with _IP_LOCK:
        if _IP_CACHE and time.time() - _IP_LAST < _IP_TTL:
            return _IP_CACHE[0]
        try:
            infos = socket.getaddrinfo("api.telegram.org", 443,
                                       socket.AF_INET, socket.SOCK_STREAM)
            _IP_CACHE = list({i[4][0] for i in infos})
            _IP_LAST = time.time()
        except Exception:
            pass
        return _IP_CACHE[0] if _IP_CACHE else None


class _TelegramConn(http.client.HTTPSConnection):
    def __init__(self, host, ip, timeout=60):
        super().__init__(ip, 443, timeout=timeout)
        self._hostname = host

    def connect(self):
        sock = socket.create_connection((self.host, self.port), self.timeout)
        ctx = ssl.create_default_context()
        self.sock = ctx.wrap_socket(sock, server_hostname=self._hostname)


def _open_conn(timeout):
    ip = _resolve_ip()
    if ip:
        return _TelegramConn("api.telegram.org", ip, timeout=timeout)
    return http.client.HTTPSConnection("api.telegram.org", 443, timeout=timeout)


def send(chat_id, text, reply_markup=None, parse_mode="HTML"):
    data = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        return api("sendMessage", data)
    except Exception as e:
        logging.error("sendMessage error: %s", e)
        return None


def now():
    return time.time()


def get_user(conn, user_id):
    return conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


def ensure_user(conn, user_id, username, lang="es"):
    u = get_user(conn, user_id)
    if not u:
        conn.execute("INSERT INTO users (user_id, username, lang, created_at) VALUES (?,?,?,?)",
                     (user_id, username, lang, now()))
        conn.commit()
        return get_user(conn, user_id)
    if u["username"] != username:
        conn.execute("UPDATE users SET username=? WHERE user_id=?", (username, user_id))
        conn.commit()
    return u


def is_premium(u):
    if u and u["user_id"] == config.ADMIN_ID:
        return True
    return bool(u and u["premium_until"] and u["premium_until"] > now())


def active_reminders(conn, user_id):
    return conn.execute(
        "SELECT * FROM reminders WHERE user_id=? AND done=0 ORDER BY due_ts",
        (user_id,)).fetchall()


def can_add(conn, user_id, u):
    if is_premium(u):
        return True, ""
    n = len(active_reminders(conn, user_id))
    if n >= config.FREE_LIMIT:
        return False, "Límite free alcanzado ({}/{})".format(n, config.FREE_LIMIT)
    return True, ""


def parse_due(raw, lang="es"):
    r = raw.strip().lower()
    now_dt = datetime.datetime.now()
    err_pasado = ("Esa hora de hoy ya pasó; usa 'mañana' o /nuevo con fecha."
                  if lang == "es" else
                  "That time already passed today; use 'tomorrow' or /nuevo with a date.")
    err_fmt = ("Formato no reconocido." if lang == "es" else "Unrecognized format.")
    try:
        if r.startswith("hoy") or r.startswith("today"):
            rest = r[4:] if r.startswith("hoy") else r[5:]
            rest = rest.strip()
            hh, mm = rest.split(":")
            due = now_dt.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
            if due < now_dt:
                return None, err_pasado
        elif (r.startswith("mañana") or r.startswith("manana") or r.startswith("tomorrow")):
            if r.startswith("tomorrow"):
                rest = r[8:].strip()
            else:
                rest = r[6:].strip()
            hh, mm = rest.split(":")
            due = (now_dt + datetime.timedelta(days=1)).replace(
                hour=int(hh), minute=int(mm), second=0, microsecond=0)
        elif " " in r and ":" in r:
            fecha, hora = r.split(" ")
            hh, mm = hora.split(":")
            partes = fecha.split("-")
            if len(partes) == 3:
                yy, mo, dd = map(int, partes)
            else:
                dd, mo = map(int, partes)
                yy = now_dt.year
            due = datetime.datetime(yy, mo, dd, int(hh), int(mm))
        elif ":" in r:
            hh, mm = r.split(":")
            due = now_dt.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
            if due < now_dt:
                due += datetime.timedelta(days=1)
        else:
            return None, err_fmt
        return due.timestamp(), ""
    except Exception:
        return None, err_fmt


def fmt_ts(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%d/%m %H:%M")


def cmd_start(conn, chat, u, text):
    send(chat["id"], T(u, "start", name=config.BOT_NAME, free=config.FREE_LIMIT))


def split_cuando(args):
    tokens = args.split()
    i = 0
    while i < len(tokens):
        t = tokens[i].lower()
        if re.match(r"^(\d{1,2}:\d{2}|\d{4}-\d{1,2}-\d{1,2}|\d{1,2}-\d{1,2})$", t) or t in (
                "hoy", "today", "mañana", "manana", "tomorrow"):
            i += 1
        else:
            break
    if i == 0:
        return None, args
    return " ".join(tokens[:i]), " ".join(tokens[i:])


def cmd_nuevo(conn, chat, u, args):
    if not args:
        send(chat["id"], T(u, "nuevo_uso"))
        return
    cuando, texto = split_cuando(args)
    if not cuando:
        send(chat["id"], T(u, "nuevo_uso"))
        return
    due_ts, err = parse_due(cuando, lang_of(u))
    if err:
        send(chat["id"], "⚠️ " + err)
        return
    text = texto or ("Recordatorio" if lang_of(u) == "es" else "Reminder")
    ok, msg = can_add(conn, u["user_id"], u)
    if not ok:
        send(chat["id"], T(u, "limite", msg=msg))
        return
    conn.execute("INSERT INTO reminders (user_id, text, due_ts, created_at) VALUES (?,?,?,?)",
                 (u["user_id"], text, due_ts, now()))
    conn.commit()
    send(chat["id"], T(u, "nuevo_ok", text=text, when=fmt_ts(due_ts)))


def cmd_lista(conn, chat, u, args):
    rows = active_reminders(conn, u["user_id"])
    if not rows:
        send(chat["id"], T(u, "lista_vacia"))
        return
    lines = [T(u, "lista_titulo")]
    for r in rows:
        lines.append("{} · {} · {}".format(r["id"], fmt_ts(r["due_ts"]), r["text"]))
    lines.append(T(u, "lista_pie"))
    send(chat["id"], "\n".join(lines))


def cmd_hoy(conn, chat, u, args):
    rows = active_reminders(conn, u["user_id"])
    hoy = datetime.date.today().strftime("%d/%m")
    out = [r for r in rows if fmt_ts(r["due_ts"]).startswith(hoy)]
    if not out:
        send(chat["id"], T(u, "hoy_vacio"))
        return
    lines = [T(u, "hoy_titulo")]
    for r in out:
        lines.append("{} · {}".format(fmt_ts(r["due_ts"]), r["text"]))
    send(chat["id"], "\n".join(lines))


def cmd_borrar(conn, chat, u, args):
    if not args:
        send(chat["id"], T(u, "borrar_uso"))
        return
    try:
        rid = int(args.strip())
    except ValueError:
        send(chat["id"], T(u, "borrar_invalido"))
        return
    cur = conn.execute("UPDATE reminders SET done=1 WHERE id=? AND user_id=?",
                       (rid, u["user_id"]))
    conn.commit()
    send(chat["id"], T(u, "borrar_ok") if cur.rowcount else T(u, "borrar_no"))


def cmd_premium(conn, chat, u, args):
    if u["user_id"] == config.ADMIN_ID:
        send(chat["id"], T(u, "premium_owner"))
        return
    if is_premium(u):
        hasta = datetime.datetime.fromtimestamp(u["premium_until"]).strftime("%d/%m/%Y")
        send(chat["id"], T(u, "premium_ya", until=hasta))
        return
    send(chat["id"], T(u, "premium_info",
                       price=config.PREMIUM_PRICE_STARS, days=config.PREMIUM_DAYS))
    payload = "prem_{}_{}".format(u["user_id"], int(now()))
    prices = [{"label": "Premium {} días".format(config.PREMIUM_DAYS),
               "amount": config.PREMIUM_PRICE_STARS}]
    inv = {"chat_id": chat["id"],
           "title": "Premium {} días".format(config.PREMIUM_DAYS),
           "description": "Recordatorios ilimitados con prioridad.",
           "payload": payload,
           "currency": "XTR",
           "prices": prices,
           "provider_token": ""}
    try:
        api("sendInvoice", inv)
    except Exception as e:
        logging.error("sendInvoice error: %s", e)
        send(chat["id"], ("⚠️ No pude lanzar el pago. Inténtalo más tarde."
                          if lang_of(u) == "es" else
                          "⚠️ I couldn't open the payment. Try again later."))


def cmd_invoice_test(conn, chat, u, args):
    if u["user_id"] != config.ADMIN_ID:
        send(chat["id"], T(u, "no_auth"))
        return
    send(chat["id"], T(u, "test_factura"))
    payload = "prem_{}_{}".format(u["user_id"], int(now()))
    prices = [{"label": "Premium {} días".format(config.PREMIUM_DAYS),
               "amount": config.PREMIUM_PRICE_STARS}]
    inv = {"chat_id": chat["id"],
           "title": "Premium {} días".format(config.PREMIUM_DAYS),
           "description": "Recordatorios ilimitados con prioridad.",
           "payload": payload,
           "currency": "XTR",
           "prices": prices,
           "provider_token": ""}
    try:
        api("sendInvoice", inv)
    except Exception as e:
        logging.error("invoice-test error: %s", e)
        send(chat["id"], ("⚠️ No pude lanzar la factura."
                          if lang_of(u) == "es" else
                          "⚠️ I couldn't open the invoice."))


def cmd_stats(conn, chat, u, args):
    if u["user_id"] != config.ADMIN_ID:
        send(chat["id"], T(u, "no_auth"))
        return
    n_users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    n_prem = conn.execute("SELECT COUNT(*) c FROM users WHERE premium_until>?",
                          (now(),)).fetchone()["c"]
    n_rem = conn.execute("SELECT COUNT(*) c FROM reminders WHERE done=0").fetchone()["c"]
    rev = conn.execute("SELECT COALESCE(SUM(stars),0) s FROM transactions").fetchone()["s"]
    n_ref = conn.execute("SELECT COUNT(*) c FROM referrals").fetchone()["c"]
    send(chat["id"], T(u, "stats_titulo", users=n_users, p=n_prem, r=n_rem, ref=n_ref, rev=rev))


def grant_premium(conn, user_id, days=None):
    days = days or config.PREMIUM_DAYS
    u = get_user(conn, user_id)
    if not u:
        return None
    base = u["premium_until"] if u["premium_until"] else now()
    if base < now():
        base = now()
    nuevo = base + days * 86400
    conn.execute("UPDATE users SET premium_until=? WHERE user_id=?", (nuevo, user_id))
    conn.commit()
    return nuevo


def handle_ref(conn, u, args):
    if not args or not args.startswith("ref_"):
        return
    try:
        inviter_id = int(args.split("_", 1)[1])
    except ValueError:
        return
    if inviter_id == u["user_id"]:
        return
    if not get_user(conn, inviter_id):
        return
    if conn.execute("SELECT 1 FROM referrals WHERE referred_id=?",
                    (u["user_id"],)).fetchone():
        return
    n = conn.execute("SELECT COUNT(*) c FROM referrals WHERE inviter_id=?",
                     (inviter_id,)).fetchone()["c"]
    if n >= config.MAX_REWARD_REFS:
        return
    conn.execute("INSERT INTO referrals (inviter_id, referred_id, created_at) VALUES (?,?,?)",
                 (inviter_id, u["user_id"], now()))
    conn.commit()
    nuevo = grant_premium(conn, inviter_id)
    if nuevo:
        hasta = datetime.datetime.fromtimestamp(nuevo).strftime("%d/%m/%Y")
        u_inv = get_user(conn, inviter_id)
        send(inviter_id, T(u_inv, "ref_inviter", until=hasta))
    send(u["user_id"], T(u, "ref_welcome"))


def cmd_compartir(conn, chat, u, args):
    link = "https://t.me/{}/?start=ref_{}".format("MementoPro_Bot", u["user_id"])
    share = "https://t.me/share/url?url=" + urllib.parse.quote(link)
    send(chat["id"],
         T(u, "compartir", days=config.PREMIUM_DAYS, max=config.MAX_REWARD_REFS, link=link),
         reply_markup={"inline_keyboard": [[{"text": "🔗 Compartir", "url": share}]]})


def on_payment(conn, chat, u, sp):
    stars = sp.get("total_amount", 0)
    payload = sp.get("invoice_payload", "")
    nuevo = grant_premium(conn, u["user_id"])
    conn.execute("INSERT INTO transactions (user_id, stars, payload, created_at) VALUES (?,?,?,?)",
                 (u["user_id"], stars, payload, now()))
    conn.commit()
    hasta = datetime.datetime.fromtimestamp(nuevo).strftime("%d/%m/%Y")
    send(chat["id"], T(u, "pago_ok", until=hasta))


def fire_due(conn):
    rows = conn.execute("SELECT * FROM reminders WHERE done=0 AND due_ts<=?",
                        (now(),)).fetchall()
    for r in rows:
        try:
            send(r["user_id"], "🔔 <b>{}</b>".format(r["text"]))
            conn.execute("UPDATE reminders SET done=1 WHERE id=?", (r["id"],))
        except Exception as e:
            logging.error("fire error: %s", e)
    if rows:
        conn.commit()


def handle_message(conn, msg):
    chat = msg.get("chat") or {}
    from_ = msg.get("from") or {}
    uid = from_.get("id") or chat.get("id")
    username = from_.get("username") or ""
    lang = (from_.get("language_code") or "es")[:2].lower()
    if lang not in ("es", "en"):
        lang = "es"
    u = ensure_user(conn, uid, username, lang)
    if "successful_payment" in msg:
        on_payment(conn, chat, u, msg["successful_payment"])
        return
    text = msg.get("text") or ""
    if not text:
        return
    args = text.strip()
    cmd = args.split()[0].lower()
    rest = args[len(cmd):].strip()
    if cmd == "/start":
        handle_ref(conn, u, rest)
        cmd_start(conn, chat, u, rest)
    elif cmd in ("/nuevo", "/add", "/new"):
        cmd_nuevo(conn, chat, u, rest)
    elif cmd in ("/lista", "/list"):
        cmd_lista(conn, chat, u, rest)
    elif cmd in ("/hoy", "/today"):
        cmd_hoy(conn, chat, u, rest)
    elif cmd in ("/borrar", "/delete", "/del"):
        cmd_borrar(conn, chat, u, rest)
    elif cmd == "/premium":
        cmd_premium(conn, chat, u, rest)
    elif cmd in ("/compartir", "/share"):
        cmd_compartir(conn, chat, u, rest)
    elif cmd in ("/invoice-test",):
        cmd_invoice_test(conn, chat, u, rest)
    elif cmd == "/stats":
        cmd_stats(conn, chat, u, rest)
    elif cmd in ("/help",):
        cmd_start(conn, chat, u, rest)
    else:
        send(chat.get("id"), T(u, "desconocido"))


def poller():
    global OFFSET
    fails = 0
    while True:
        try:
            res = api("getUpdates", {"offset": OFFSET, "timeout": 10,
                                     "allowed_updates": ["message", "pre_checkout_query"]},
                      timeout=15)
            for upd in res.get("result", []):
                OFFSET = upd["update_id"] + 1
                UPDATE_QUEUE.put(upd)
            fails = 0
        except Exception as e:
            logging.error("poll error: %s", e)
            fails += 1
            time.sleep(min(2 * fails, 10))


def worker():
    conn = db()
    while True:
        upd = UPDATE_QUEUE.get()
        try:
            if "message" in upd:
                handle_message(conn, upd["message"])
            elif "pre_checkout_query" in upd:
                q = upd["pre_checkout_query"]
                api("answerPreCheckoutQuery",
                    {"pre_checkout_query_id": q["id"], "ok": True})
        except Exception as e:
            logging.error("worker error: %s", e)
        UPDATE_QUEUE.task_done()


def ticker():
    while True:
        time.sleep(10)
        try:
            conn = db()
            fire_due(conn)
            conn.close()
        except Exception as e:
            logging.error("ticker error: %s", e)


def main():
    init_db()
    username = None
    for i in range(30):
        try:
            username = api("getMe", timeout=20).get("result", {}).get("username")
            break
        except Exception as e:
            logging.error("getMe retry %d: %s", i, e)
            time.sleep(3)
    logging.info("bot %s arrancado (%s)", username, TOKEN[:8])
    threads = [threading.Thread(target=poller, daemon=True)]
    for _ in range(WORKERS):
        threads.append(threading.Thread(target=worker, daemon=True))
    threads.append(threading.Thread(target=ticker, daemon=True))
    for t in threads:
        t.start()
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
