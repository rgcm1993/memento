import os

BASE = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(BASE, "token.txt")
DB = os.path.join(BASE, "db.sqlite3")
LOG = os.path.join(BASE, "bot.log")

ADMIN_FILE = os.path.join(BASE, "admin.txt")

def _load_admin_id():
    v = os.environ.get("ADMIN_ID")
    if v:
        return int(v)
    try:
        with open(ADMIN_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return None

ADMIN_ID = _load_admin_id()
FREE_LIMIT = 3
PREMIUM_PRICE_STARS = 100
PREMIUM_DAYS = 30
MAX_REWARD_REFS = 10
TZ = "Europe/Madrid"
BOT_NAME = "Memento"
