#!/usr/bin/env python3
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║          🎯 بوت صيد يوزرات تيليجرام الاحترافي                             ║
# ║          الإصدار: 5.0.0 | المطور: @og5_i                                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

import os, sys, asyncio, aiosqlite, aiohttp, json, logging, random
import re, string, time, uuid, shutil
from datetime import datetime, timedelta
from typing import Optional
from functools import wraps
from collections import defaultdict
from threading import Thread

from flask import Flask
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    BotCommand, LabeledPrice
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    PreCheckoutQueryHandler, MessageHandler, filters, ContextTypes
)
from telegram.constants import ParseMode

# ══════════════════════════════════════════════════════════════════════
#  ⚙️ الإعدادات الرئيسية
# ══════════════════════════════════════════════════════════════════════

BOT_TOKEN  = "8430646995:AAGcLW926BWCzYLHBeB36X6GKRVA_h5t2Hg"
ADMIN_ID   = 8112511629
DEV_TAG    = "@og5_i"
BOT_VER    = "5.0.0"
BOT_NAME   = "🎯 Hunter Pro"

DB_PATH    = "data/bot.db"
LOG_PATH   = "data/bot.log"
BCK_DIR    = "data/backups"

os.makedirs("data", exist_ok=True)
os.makedirs(BCK_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════
#  💳 أسعار النجوم (معقولة جداً)
# ══════════════════════════════════════════════════════════════════════

PLANS = {
    "trial":   {"stars": 15,   "days": 1,    "emoji": "🆓", "name": "تجريبي",  "desc": "1 يوم"},
    "weekly":  {"stars": 50,   "days": 7,    "emoji": "📅", "name": "أسبوعي",  "desc": "7 أيام"},
    "monthly": {"stars": 150,  "days": 30,   "emoji": "📆", "name": "شهري",    "desc": "30 يوم"},
    "pro":     {"stars": 350,  "days": 90,   "emoji": "⭐", "name": "برو",     "desc": "90 يوم"},
    "yearly":  {"stars": 800,  "days": 365,  "emoji": "💎", "name": "سنوي",    "desc": "365 يوم"},
    "forever": {"stars": 2000, "days": 36500,"emoji": "♾️", "name": "مدى الحياة","desc": "دائم"},
}

# ══════════════════════════════════════════════════════════════════════
#  🔧 ثوابت المحرك
# ══════════════════════════════════════════════════════════════════════

FLOOD_MIN     = 1.2
FLOOD_MAX     = 3.5
CHECK_TIMEOUT = 12
MAX_CONC      = 5
VERIFY_TIMES  = 2
CACHE_HOURS   = 48

RESERVED = {
    "telegram","admin","support","help","settings","info","bot","bots","store",
    "channel","group","sticker","stickers","gif","test","login","signup","register",
    "api","web","app","mobile","desktop","game","games","music","video","photo",
    "news","shop","pay","wallet","crypto","bank","null","true","false","root",
    "user","users","name","username","void","system","official","team","staff",
}

# ══════════════════════════════════════════════════════════════════════
#  📝 LOGGING
# ══════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("HunterBot")

# ══════════════════════════════════════════════════════════════════════
#  🌐 FLASK KEEP-ALIVE
# ══════════════════════════════════════════════════════════════════════

_app = Flask(__name__)

@_app.route("/")
def _home():
    return (
        f"<html><body style='font-family:Arial;text-align:center;padding:40px'>"
        f"<h1>🤖 {BOT_NAME}</h1>"
        f"<h2 style='color:green'>✅ يعمل بشكل طبيعي</h2>"
        f"<p>🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
        f"<p>📦 الإصدار: {BOT_VER} | 👨‍💻 {DEV_TAG}</p>"
        f"</body></html>"
    )

@_app.route("/health")
def _health():
    return {"status": "alive", "version": BOT_VER, "bot": BOT_NAME, "time": str(datetime.now())}

@_app.route("/ping")
def _ping():
    return "pong"

def _run_flask():
    _app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

def keep_alive():
    Thread(target=_run_flask, daemon=True).start()
    logger.info("🌐 Flask keep-alive: port 5000")

# ══════════════════════════════════════════════════════════════════════
#  🗄️ DATABASE
# ══════════════════════════════════════════════════════════════════════

class DB:
    _conn: Optional[aiosqlite.Connection] = None

    async def init(self):
        self._conn = await aiosqlite.connect(DB_PATH)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA cache_size=10000")
        await self._conn.execute("PRAGMA temp_store=MEMORY")
        await self._mk_tables()
        logger.info("✅ قاعدة البيانات جاهزة")

    async def _mk_tables(self):
        sql = """
        CREATE TABLE IF NOT EXISTS users (
            uid            INTEGER PRIMARY KEY,
            uname          TEXT,
            fname          TEXT,
            lname          TEXT,
            plan           TEXT    DEFAULT 'none',
            plan_end       TEXT,
            is_banned      INTEGER DEFAULT 0,
            ban_reason     TEXT,
            is_vip         INTEGER DEFAULT 0,
            is_admin2      INTEGER DEFAULT 0,
            lang           TEXT    DEFAULT 'ar',
            total_hunts    INTEGER DEFAULT 0,
            total_found    INTEGER DEFAULT 0,
            total_paid     INTEGER DEFAULT 0,
            joined_at      TEXT    DEFAULT (datetime('now')),
            last_active    TEXT    DEFAULT (datetime('now')),
            notified_exp   INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS found_names (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    UNIQUE,
            len         INTEGER,
            found_by    INTEGER,
            rarity      REAL    DEFAULT 0,
            is_rare     INTEGER DEFAULT 0,
            verified    INTEGER DEFAULT 0,
            found_at    TEXT    DEFAULT (datetime('now')),
            status      TEXT    DEFAULT 'available'
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            uid      INTEGER,
            type     TEXT,
            checked  INTEGER DEFAULT 0,
            found    INTEGER DEFAULT 0,
            status   TEXT    DEFAULT 'running',
            started  TEXT    DEFAULT (datetime('now')),
            ended    TEXT
        );
        CREATE TABLE IF NOT EXISTS cache (
            username   TEXT PRIMARY KEY,
            status     TEXT,
            checked_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS payments (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            uid       INTEGER,
            action    TEXT,
            plan      TEXT,
            days      INTEGER,
            stars     INTEGER DEFAULT 0,
            by_admin  INTEGER DEFAULT 0,
            note      TEXT,
            created   TEXT    DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS broadcasts (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            msg     TEXT,
            target  TEXT,
            sent    INTEGER DEFAULT 0,
            failed  INTEGER DEFAULT 0,
            at      TEXT    DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS adm_log (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            admin   INTEGER,
            action  TEXT,
            detail  TEXT,
            at      TEXT    DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS stats_daily (
            date     TEXT PRIMARY KEY,
            checks   INTEGER DEFAULT 0,
            found    INTEGER DEFAULT 0,
            users    INTEGER DEFAULT 0,
            stars    INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_found_len   ON found_names(len);
        CREATE INDEX IF NOT EXISTS idx_found_rare  ON found_names(rarity);
        CREATE INDEX IF NOT EXISTS idx_users_plan  ON users(plan);
        CREATE INDEX IF NOT EXISTS idx_users_ban   ON users(is_banned);
        """
        await self._conn.executescript(sql)
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()

    async def run(self, q, p=None):
        c = await self._conn.execute(q, p or [])
        await self._conn.commit()
        return c

    async def one(self, q, p=None):
        c = await self._conn.execute(q, p or [])
        return await c.fetchone()

    async def all(self, q, p=None):
        c = await self._conn.execute(q, p or [])
        return await c.fetchall()

    async def val(self, q, p=None, default=0):
        r = await self.one(q, p)
        return r[0] if r else default

db = DB()

# ══════════════════════════════════════════════════════════════════════
#  🛡️ SPAM GUARD
# ══════════════════════════════════════════════════════════════════════

class SpamGuard:
    def __init__(self):
        self._log: dict[int, list] = defaultdict(list)
        self.RPM = 25

    def ok(self, uid: int) -> bool:
        if uid == ADMIN_ID:
            return True
        now = time.time()
        self._log[uid] = [t for t in self._log[uid] if now - t < 60]
        if len(self._log[uid]) >= self.RPM:
            return False
        self._log[uid].append(now)
        return True

guard = SpamGuard()

# ══════════════════════════════════════════════════════════════════════
#  🔍 USERNAME CHECKER
# ══════════════════════════════════════════════════════════════════════

class Checker:
    def __init__(self):
        self._sess: Optional[aiohttp.ClientSession] = None
        self._sem  = asyncio.Semaphore(MAX_CONC)
        self.checked = 0
        self.found   = 0
        self.errors  = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self._sess or self._sess.closed:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            }
            conn = aiohttp.TCPConnector(ssl=False, limit=MAX_CONC, ttl_dns_cache=300)
            tout = aiohttp.ClientTimeout(total=CHECK_TIMEOUT, connect=5)
            self._sess = aiohttp.ClientSession(headers=headers, timeout=tout, connector=conn)
        return self._sess

    async def close(self):
        if self._sess and not self._sess.closed:
            await self._sess.close()

    def validate(self, username: str) -> tuple[bool, str]:
        u = username.strip().lstrip("@")
        if len(u) < 3:
            return False, "⚠️ اليوزر قصير جداً — الحد الأدنى 3 أحرف"
        if len(u) > 32:
            return False, "⚠️ اليوزر طويل — الحد الأقصى 32 حرف"
        if not u[0].isalpha():
            return False, "⚠️ يجب أن يبدأ اليوزر بحرف (a-z A-Z)"
        if not re.match(r'^[a-zA-Z0-9_]+$', u):
            return False, "⚠️ يُسمح فقط بـ: حروف لاتينية — أرقام — شرطة سفلية _"
        if "__" in u:
            return False, "⚠️ لا يُسمح بشرطتين سفليتين متتاليتين (__)"
        if u.startswith("_") or u.endswith("_"):
            return False, "⚠️ لا يمكن أن يبدأ أو ينتهي اليوزر بشرطة سفلية"
        if u.lower() in RESERVED:
            return False, "⚠️ هذا اليوزر محجوز من تيليجرام"
        return True, ""

    def rarity_score(self, u: str) -> float:
        n = len(u)
        score = {3: 95.0, 4: 72.0, 5: 42.0}.get(n, 20.0)
        if re.match(r'^[a-z]+$', u):          score += 10.0
        if u.isalpha():                        score += 8.0
        if re.match(r'^[a-z][0-9]+$', u):     score += 5.0
        if n == 3 and u.isalpha():             score += 5.0
        words = ["vip","pro","top","max","win","king","god","uae","ksa","fox","ace","sky","fly","ray"]
        for w in words:
            if w in u.lower():
                score += 12.0
                break
        return min(round(score, 1), 100.0)

    async def check(self, username: str) -> dict:
        async with self._sem:
            r = {"username": username, "available": False, "error": None}
            valid, err = self.validate(username)
            if not valid:
                r["error"] = err
                return r

            # Check cache
            cached = await db.one(
                "SELECT status, checked_at FROM cache WHERE username=?", (username.lower(),)
            )
            if cached:
                try:
                    age = (datetime.now() - datetime.fromisoformat(cached["checked_at"])).total_seconds()
                    if age < CACHE_HOURS * 3600:
                        r["available"] = cached["status"] == "available"
                        return r
                except Exception:
                    pass

            sess = await self._get_session()
            url  = f"https://t.me/{username}"
            self.checked += 1

            for attempt in range(3):
                try:
                    async with sess.get(url, allow_redirects=True) as resp:
                        if resp.status == 404:
                            r["available"] = True
                        elif resp.status == 200:
                            text = await resp.text(errors="ignore")
                            taken_signals = [
                                "tgme_page_extra",
                                "tgme_header_title",
                                "tgme_page_title",
                                "tgme_icon_user",
                                "tgme_icon_channel",
                                "tgme_icon_group",
                                '"og:title"',
                                'property="og:title"',
                                f'"@{username.lower()}"',
                            ]
                            r["available"] = not any(s in text for s in taken_signals)
                        else:
                            r["available"] = False

                        # Update cache
                        status = "available" if r["available"] else "taken"
                        await db.run(
                            "INSERT OR REPLACE INTO cache (username,status,checked_at) VALUES (?,?,?)",
                            (username.lower(), status, datetime.now().isoformat())
                        )
                        return r

                except asyncio.TimeoutError:
                    r["error"] = "⏰ انتهت مهلة الاتصال"
                except aiohttp.ClientConnectorError:
                    r["error"] = "🔌 خطأ في الاتصال بالإنترنت"
                except Exception as e:
                    r["error"] = f"❌ {str(e)[:50]}"

                if attempt < 2:
                    await asyncio.sleep(random.uniform(1.0, 2.5))

            self.errors += 1
            return r

    async def verify(self, username: str) -> bool:
        ok = 0
        for i in range(VERIFY_TIMES):
            r = await self.check(username)
            if r["available"] and not r["error"]:
                ok += 1
            if i < VERIFY_TIMES - 1:
                await asyncio.sleep(random.uniform(FLOOD_MIN, FLOOD_MAX))
        return ok == VERIFY_TIMES

    def reset(self):
        self.checked = 0
        self.found   = 0
        self.errors  = 0

chk = Checker()

# ══════════════════════════════════════════════════════════════════════
#  🎯 HUNT ENGINE
# ══════════════════════════════════════════════════════════════════════

class HuntEngine:
    def __init__(self):
        self.active: dict[str, dict] = {}

    def _generate(self, length: int, count: int, mode: str, prefix="", suffix="") -> list:
        if mode == "alpha":
            pool = string.ascii_lowercase
        elif mode == "digits":
            pool = string.digits
        elif mode == "mixed":
            pool = string.ascii_lowercase + string.digits
        else:
            pool = string.ascii_lowercase + string.digits

        results, seen, tries = [], set(), 0
        max_tries = count * 20

        while len(results) < count and tries < max_tries:
            tries += 1
            body_len = length - len(prefix) - len(suffix)
            if body_len <= 0:
                continue

            body  = "".join(random.choice(pool) for _ in range(body_len))
            uname = prefix + body + suffix

            # Ensure starts with letter
            if not uname[0].isalpha():
                if not prefix:
                    uname = random.choice(string.ascii_lowercase) + uname[1:]
                else:
                    continue

            if len(uname) != length:
                continue
            if uname in seen:
                continue
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', uname):
                continue

            seen.add(uname)
            results.append(uname)

        return results

    async def start(
        self, uid: int, length: int, count: int, mode: str,
        ctx: ContextTypes.DEFAULT_TYPE, chat_id: int,
        prefix: str = "", suffix: str = ""
    ) -> str:
        hid = str(uuid.uuid4())[:6].upper()
        self.active[hid] = {
            "uid": uid, "status": "running",
            "checked": 0, "found": 0,
            "total": count, "t0": time.time(),
            "results": []
        }

        sid_cur = await db.run(
            "INSERT INTO sessions (uid,type,status) VALUES (?,?,?)",
            (uid, f"{length}char_{mode}", "running")
        )
        sid = sid_cur.lastrowid

        usernames = self._generate(length, count, mode, prefix, suffix)
        if not usernames:
            self.active[hid]["status"] = "done"
            return hid

        chk.reset()
        found_list = []

        # إرسال رسالة التقدم
        try:
            pmsg = await ctx.bot.send_message(
                chat_id, self._prog_text(hid, 0, len(usernames), 0, 0.01),
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pmsg = None

        last_upd = time.time()

        for i, uname in enumerate(usernames):
            if self.active.get(hid, {}).get("status") == "stopped":
                break

            r = await chk.check(uname)

            if r["available"] and not r.get("error"):
                confirmed = await chk.verify(uname)
                if confirmed:
                    rar  = chk.rarity_score(uname)
                    rare = rar >= 80
                    try:
                        await db.run(
                            "INSERT OR IGNORE INTO found_names (username,len,found_by,rarity,is_rare,verified) VALUES (?,?,?,?,?,?)",
                            (uname, length, uid, rar, int(rare), VERIFY_TIMES)
                        )
                    except Exception:
                        pass

                    chk.found += 1
                    self.active[hid]["found"] += 1
                    found_list.append({"u": uname, "r": rar, "rare": rare})

                    em = "💎" if rare else "✅"
                    alert = (
                        f"{em} <b>يوزر متاح ومؤكد!</b>\n\n"
                        f"📛 <code>@{uname}</code>\n"
                        f"📏 الطول: {length} أحرف\n"
                        f"⭐ الندرة: {rar}%\n"
                        f"🔍 تحقق: {VERIFY_TIMES}×\n"
                        f"🕐 {datetime.now().strftime('%H:%M:%S')}\n\n"
                        f"➡️ t.me/{uname}"
                    )
                    try:
                        await ctx.bot.send_message(chat_id, alert, parse_mode=ParseMode.HTML)
                    except Exception:
                        pass

                    if rare and chat_id != ADMIN_ID:
                        try:
                            await ctx.bot.send_message(
                                ADMIN_ID,
                                f"💎 <b>يوزر نادر!</b>\n<code>@{uname}</code> — {rar}%\n👤 {uid}",
                                parse_mode=ParseMode.HTML
                            )
                        except Exception:
                            pass

            self.active[hid]["checked"] = i + 1
            elapsed = time.time() - self.active[hid]["t0"]

            if pmsg and (time.time() - last_upd) >= 4.0:
                try:
                    await pmsg.edit_text(
                        self._prog_text(hid, i+1, len(usernames), self.active[hid]["found"], elapsed),
                        parse_mode=ParseMode.HTML
                    )
                    last_upd = time.time()
                except Exception:
                    pass

            await asyncio.sleep(random.uniform(FLOOD_MIN, FLOOD_MAX))

        # انتهى الصيد
        elapsed = time.time() - self.active[hid]["t0"]
        self.active[hid]["status"] = "done"
        self.active[hid]["results"] = found_list

        await db.run(
            "UPDATE sessions SET ended=?,checked=?,found=?,status=? WHERE id=?",
            (datetime.now().isoformat(), len(usernames), len(found_list), "done", sid)
        )
        await db.run(
            "UPDATE users SET total_hunts=total_hunts+1, total_found=total_found+?, last_active=? WHERE uid=?",
            (len(found_list), datetime.now().isoformat(), uid)
        )

        if pmsg:
            try:
                await pmsg.edit_text(
                    self._final_text(hid, len(usernames), found_list, elapsed),
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                pass

        return hid

    def _prog_text(self, hid, cur, total, found, elapsed):
        pct  = int(cur / total * 100) if total else 0
        bar  = "█" * (pct // 5) + "░" * (20 - pct // 5)
        spd  = cur / elapsed if elapsed > 0.1 else 0
        eta  = int((total - cur) / spd) if spd > 0 else 0
        return (
            f"🔍 <b>جاري الصيد</b> — <code>[{hid}]</code>\n\n"
            f"<code>[{bar}] {pct}%</code>\n\n"
            f"📊 تم فحص: <b>{cur} / {total}</b>\n"
            f"✅ متاح:   <b>{found}</b>\n"
            f"⚡ السرعة: <b>{spd:.1f}</b> يوزر/ثانية\n"
            f"⏱ مضى:    <b>{int(elapsed)}ث</b>\n"
            f"⏳ متبقي:  <b>~{eta}ث</b>\n\n"
            f"🔄 <i>جاري الفحص...</i>"
        )

    def _final_text(self, hid, total, found_list, elapsed):
        txt = (
            f"📋 <b>تقرير الصيد</b> — <code>[{hid}]</code>\n"
            f"{'━'*30}\n"
            f"📊 فُحص: <b>{total}</b>   ✅ متاح: <b>{len(found_list)}</b>\n"
            f"⏱ المدة: <b>{int(elapsed)} ثانية</b>\n"
            f"{'━'*30}\n\n"
        )
        if found_list:
            txt += "🎯 <b>اليوزرات المتاحة:</b>\n\n"
            for x in found_list:
                em = "💎" if x["rare"] else "✅"
                txt += f"{em} <code>@{x['u']}</code> — ندرة: {x['r']}%\n"
        else:
            txt += "❌ لم يُعثر على يوزرات متاحة في هذه الجولة.\n💡 جرّب مرة أخرى!"
        txt += f"\n\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n👨‍💻 {DEV_TAG}"
        return txt

    def stop(self, hid: str):
        if hid in self.active:
            self.active[hid]["status"] = "stopped"

    def stop_all(self):
        for h in self.active.values():
            h["status"] = "stopped"

    def stop_user(self, uid: int):
        for h in self.active.values():
            if h["uid"] == uid and h["status"] == "running":
                h["status"] = "stopped"

    def user_active(self, uid: int) -> bool:
        return any(h["uid"] == uid and h["status"] == "running" for h in self.active.values())

engine = HuntEngine()

# ══════════════════════════════════════════════════════════════════════
#  🛠️ HELPERS
# ══════════════════════════════════════════════════════════════════════

async def reg_user(user):
    ex = await db.one("SELECT uid FROM users WHERE uid=?", (user.id,))
    if not ex:
        await db.run(
            "INSERT INTO users (uid,uname,fname,lname) VALUES (?,?,?,?)",
            (user.id, user.username, user.first_name, user.last_name)
        )
    else:
        await db.run(
            "UPDATE users SET uname=?,fname=?,lname=?,last_active=? WHERE uid=?",
            (user.username, user.first_name, user.last_name, datetime.now().isoformat(), user.id)
        )

async def get_user(uid: int):
    return await db.one("SELECT * FROM users WHERE uid=?", (uid,))

async def has_sub(uid: int) -> bool:
    if uid == ADMIN_ID:
        return True
    u = await get_user(uid)
    if not u or u["is_banned"] or u["plan"] == "none" or not u["plan_end"]:
        return False
    try:
        return datetime.now() < datetime.fromisoformat(u["plan_end"])
    except Exception:
        return False

async def sub_info(uid: int) -> str:
    if uid == ADMIN_ID:
        return "👑 مدير — اشتراك دائم"
    u = await get_user(uid)
    if not u or u["plan"] == "none" or not u["plan_end"]:
        return "❌ لا اشتراك"
    try:
        end  = datetime.fromisoformat(u["plan_end"])
        left = (end - datetime.now()).days
        if left < 0:
            return "❌ منتهي"
        plan = PLANS.get(u["plan"], {})
        em   = plan.get("emoji", "📦")
        return f"{em} {plan.get('name', u['plan'])} — {left} يوم"
    except Exception:
        return "❓ غير معروف"

def admin_only(f):
    @wraps(f)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("⛔ هذا الأمر للمدير فقط.")
            return
        return await f(update, ctx)
    return wrapper

def sub_only(f):
    @wraps(f)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid == ADMIN_ID:
            return await f(update, ctx)
        if not guard.ok(uid):
            return await update.message.reply_text("⚠️ طلبات كثيرة — انتظر دقيقة.")
        u = await get_user(uid)
        if not u:
            return await update.message.reply_text("استخدم /start أولاً.")
        if u["is_banned"]:
            return await update.message.reply_text(f"🚫 أنت محظور.\nالسبب: {u['ban_reason'] or '—'}")
        if not await has_sub(uid):
            return await update.message.reply_text(
                "⛔ <b>تحتاج اشتراكاً لاستخدام هذه الميزة.</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💳 اشترِ الآن ⭐", callback_data="menu_buy")
                ]])
            )
        return await f(update, ctx)
    return wrapper

def anti_spam(f):
    @wraps(f)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid != ADMIN_ID and not guard.ok(uid):
            return await update.message.reply_text("⚠️ بطئ — طلبات كثيرة.")
        return await f(update, ctx)
    return wrapper

# ══════════════════════════════════════════════════════════════════════
#  💳 STARS PAYMENT HANDLERS
# ══════════════════════════════════════════════════════════════════════

async def send_invoice(ctx, chat_id: int, plan_key: str):
    p = PLANS[plan_key]
    await ctx.bot.send_invoice(
        chat_id=chat_id,
        title=f"{p['emoji']} اشتراك {p['name']}",
        description=(
            f"✅ اشتراك {p['name']} في {BOT_NAME}\n"
            f"⏱ المدة: {p['desc']}\n"
            f"🎯 صيد يوزرات 3-5 أحرف بدون قيود\n"
            f"⚡ تحقق مزدوج — نتائج حقيقية\n"
            f"👨‍💻 {DEV_TAG}"
        ),
        payload=f"sub_{plan_key}_{chat_id}_{int(time.time())}",
        provider_token="",   # فارغ = نجوم تيليجرام
        currency="XTR",      # XTR = Stars
        prices=[LabeledPrice(label=f"{p['emoji']} {p['name']}", amount=p["stars"])],
    )

async def pre_checkout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.pre_checkout_query
    payload = q.invoice_payload or ""
    if payload.startswith("sub_"):
        parts = payload.split("_")
        if len(parts) >= 2 and parts[1] in PLANS:
            await q.answer(ok=True)
            return
    await q.answer(ok=False, error_message="❌ فشل التحقق من الدفع — حاول مجدداً.")

async def successful_payment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    pay   = update.message.successful_payment
    stars = pay.total_amount
    parts = pay.invoice_payload.split("_")

    plan_key = parts[1] if len(parts) >= 2 and parts[1] in PLANS else "monthly"
    p    = PLANS[plan_key]
    days = p["days"]

    # تمديد أو تفعيل جديد
    u = await get_user(uid)
    if not u:
        await reg_user(update.effective_user)
        u = await get_user(uid)

    if u and u["plan_end"]:
        try:
            cur_end = datetime.fromisoformat(u["plan_end"])
            base    = max(cur_end, datetime.now())
        except Exception:
            base = datetime.now()
    else:
        base = datetime.now()

    new_end = (base + timedelta(days=days)).isoformat()
    await db.run(
        "UPDATE users SET plan=?,plan_end=?,total_paid=total_paid+?,notified_exp=0 WHERE uid=?",
        (plan_key, new_end, stars, uid)
    )
    await db.run(
        "INSERT INTO payments (uid,action,plan,days,stars) VALUES (?,?,?,?,?)",
        (uid, "stars_buy", plan_key, days, stars)
    )

    await update.message.reply_text(
        f"🎉 <b>تم الدفع بنجاح!</b>\n\n"
        f"{p['emoji']} الخطة: <b>{p['name']}</b>\n"
        f"⭐ النجوم: <b>{stars}</b>\n"
        f"📅 المدة: <b>{p['desc']}</b>\n"
        f"⏰ ينتهي: <b>{new_end[:10]}</b>\n\n"
        f"ابدأ الصيد الآن! /hunt\n"
        f"👨‍💻 {DEV_TAG}",
        parse_mode=ParseMode.HTML
    )

    # إشعار المدير
    try:
        name = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.first_name
        await ctx.bot.send_message(
            ADMIN_ID,
            f"💰 <b>دفعة جديدة!</b>\n"
            f"👤 {name} — <code>{uid}</code>\n"
            f"{p['emoji']} {p['name']} — {p['desc']}\n"
            f"⭐ {stars} نجمة",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════
#  📋 USER COMMANDS
# ══════════════════════════════════════════════════════════════════════

@anti_spam
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await reg_user(u)
    sub = await sub_info(u.id)
    is_adm = u.id == ADMIN_ID

    txt = (
        f"👋 <b>أهلاً {u.first_name}!</b>\n\n"
        f"{'━'*32}\n"
        f"🤖 <b>{BOT_NAME}</b> — v{BOT_VER}\n"
        f"{'━'*32}\n\n"
        f"🎯 <b>ما الذي يمكنني فعله؟</b>\n\n"
        f"💎 صيد يوزرات <b>3 أحرف</b> (نادرة جداً)\n"
        f"⭐ صيد يوزرات <b>4 أحرف</b> (نادرة)\n"
        f"✅ صيد يوزرات <b>5 أحرف</b> (متاحة)\n\n"
        f"🔍 تحقق مزدوج — نتائج حقيقية ١٠٠٪\n"
        f"💳 دفع بنجوم تيليجرام مباشرة\n\n"
        f"{'━'*32}\n"
        f"📋 اشتراكك: {sub}\n"
        f"👨‍💻 المطور: {DEV_TAG}\n"
    )

    kb = [
        [InlineKeyboardButton("🎯 ابدأ الصيد", callback_data="menu_hunt"),
         InlineKeyboardButton("💳 اشترِ اشتراكاً", callback_data="menu_buy")],
        [InlineKeyboardButton("📊 إحصائياتي",    callback_data="menu_stats"),
         InlineKeyboardButton("💎 يوزراتي",      callback_data="menu_found")],
        [InlineKeyboardButton("📋 اشتراكي",      callback_data="menu_sub"),
         InlineKeyboardButton("❓ مساعدة",       callback_data="menu_help")],
    ]
    if is_adm:
        kb.append([InlineKeyboardButton("🔐 لوحة الإدارة ◀", callback_data="adm_panel")])

    await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

@anti_spam
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📖 <b>دليل الاستخدام</b>\n{'━'*30}\n\n"
        f"<b>أوامر المستخدم:</b>\n"
        f"• /start — القائمة الرئيسية\n"
        f"• /hunt — بدء الصيد\n"
        f"• /check [يوزر] — فحص يوزر\n"
        f"• /stop — إيقاف الصيد\n"
        f"• /stats — إحصائياتي\n"
        f"• /found — يوزراتي\n"
        f"• /sub — حالة اشتراكي\n"
        f"• /buy — شراء اشتراك\n\n"
        f"<b>صيد مخصص:</b>\n"
        f"• /custom [طول] [عدد] [نوع]\n"
        f"• /prefix [طول] [عدد] [نوع] [بادئة]\n"
        f"• /suffix [طول] [عدد] [نوع] [لاحقة]\n\n"
        f"أنواع: <code>alpha</code> <code>digits</code> <code>mixed</code>\n\n"
        f"{'━'*30}\n"
        f"💳 الدفع: نجوم تيليجرام ⭐\n"
        f"👨‍💻 {DEV_TAG} | v{BOT_VER}",
        parse_mode=ParseMode.HTML
    )

@anti_spam
async def cmd_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = []
    for k, p in PLANS.items():
        kb.append([InlineKeyboardButton(
            f"{p['emoji']} {p['name']} — {p['stars']} ⭐ ({p['desc']})",
            callback_data=f"buy_{k}"
        )])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu_back")])
    await update.message.reply_text(
        f"💳 <b>اختر خطة الاشتراك</b>\n{'━'*30}\n\n"
        f"⭐ الدفع بنجوم تيليجرام الآمنة\n"
        f"✅ تفعيل فوري بعد الدفع\n"
        f"🔄 التجديد يمدّد تلقائياً فوق الحالي\n\n"
        f"{'━'*30}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb)
    )

@sub_only
async def cmd_hunt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if engine.user_active(update.effective_user.id):
        return await update.message.reply_text(
            "⚠️ لديك عملية صيد نشطة. استخدم /stop لإيقافها أولاً."
        )
    kb = [
        [InlineKeyboardButton("3️⃣ ثلاثية 💎",  callback_data="ht_3_alpha"),
         InlineKeyboardButton("4️⃣ رباعية ⭐",  callback_data="ht_4_alpha"),
         InlineKeyboardButton("5️⃣ خماسية ✅",  callback_data="ht_5_alpha")],
        [InlineKeyboardButton("🔥 توربو 3",     callback_data="turbo_3"),
         InlineKeyboardButton("🔥 توربو 4",     callback_data="turbo_4"),
         InlineKeyboardButton("🔥 توربو 5",     callback_data="turbo_5")],
        [InlineKeyboardButton("💎 نادرة فقط 3", callback_data="ultra_3"),
         InlineKeyboardButton("💎 نادرة فقط 4", callback_data="ultra_4"),
         InlineKeyboardButton("🎲 مختلط",       callback_data="ht_4_mixed")],
        [InlineKeyboardButton("⚙️ مخصص",        callback_data="menu_custom")],
    ]
    await update.message.reply_text(
        "🎯 <b>اختر نوع الصيد:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb)
    )

@sub_only
async def cmd_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text(
            "📝 الاستخدام:\n<code>/check username</code>\nأو\n<code>/check abc def xyz</code> (حتى 5 يوزرات)",
            parse_mode=ParseMode.HTML
        )

    usernames = [a.lstrip("@").strip().lower() for a in ctx.args[:5]]
    msg = await update.message.reply_text(f"🔍 جاري فحص {len(usernames)} يوزر...", parse_mode=ParseMode.HTML)

    results = []
    for uname in usernames:
        valid, err = chk.validate(uname)
        if not valid:
            results.append(f"⚠️ <code>@{uname}</code> — {err}")
            continue

        r = await chk.check(uname)
        if r.get("error") and not r["available"]:
            results.append(f"❓ <code>@{uname}</code> — {r['error']}")
            continue

        if r["available"]:
            confirmed = await chk.verify(uname)
            if confirmed:
                rar = chk.rarity_score(uname)
                em  = "💎" if rar >= 80 else "✅"
                results.append(f"{em} <code>@{uname}</code> — متاح! ندرة: {rar}%")
            else:
                results.append(f"⚠️ <code>@{uname}</code> — غير مؤكد (ربما محجوز)")
        else:
            results.append(f"❌ <code>@{uname}</code> — محجوز")

    await msg.edit_text(
        f"🔍 <b>نتائج الفحص:</b>\n\n" + "\n".join(results),
        parse_mode=ParseMode.HTML
    )

async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    engine.stop_user(uid)
    await update.message.reply_text("🛑 تم إيقاف الصيد.")

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u   = await get_user(uid)
    if not u:
        return await update.message.reply_text("استخدم /start أولاً.")

    tf  = await db.val("SELECT COUNT(*) FROM found_names WHERE found_by=?", (uid,))
    tr  = await db.val("SELECT COUNT(*) FROM found_names WHERE found_by=? AND is_rare=1", (uid,))
    t3  = await db.val("SELECT COUNT(*) FROM found_names WHERE found_by=? AND len=3", (uid,))
    t4  = await db.val("SELECT COUNT(*) FROM found_names WHERE found_by=? AND len=4", (uid,))
    t5  = await db.val("SELECT COUNT(*) FROM found_names WHERE found_by=? AND len=5", (uid,))
    sub = await sub_info(uid)
    ts  = await db.val("SELECT COALESCE(SUM(stars),0) FROM payments WHERE uid=?", (uid,))

    await update.message.reply_text(
        f"📊 <b>إحصائياتك</b>\n{'━'*28}\n"
        f"🆔 <code>{uid}</code>\n"
        f"📋 الاشتراك: {sub}\n"
        f"⭐ نجوم دفعتها: {ts}\n"
        f"{'━'*28}\n"
        f"🎯 عمليات الصيد: {u['total_hunts']}\n"
        f"✅ مصيدة الإجمالي: {tf}\n"
        f"💎 نادرة: {tr}\n"
        f"{'━'*28}\n"
        f"3️⃣ ثلاثية: {t3}\n"
        f"4️⃣ رباعية: {t4}\n"
        f"5️⃣ خماسية: {t5}",
        parse_mode=ParseMode.HTML
    )

async def cmd_found(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    rows = await db.all(
        "SELECT * FROM found_names WHERE found_by=? ORDER BY rarity DESC LIMIT 50",
        (uid,)
    )
    if not rows:
        return await update.message.reply_text("📭 لم تصطد أي يوزرات بعد. ابدأ /hunt")

    txt = f"💎 <b>يوزراتك المصيدة</b> ({len(rows)})\n{'━'*28}\n\n"
    for r in rows:
        em = "💎" if r["is_rare"] else "✅"
        txt += f"{em} <code>@{r['username']}</code> — {r['len']}ح — {r['rarity']}%\n"

    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)

async def cmd_sub(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u   = await get_user(uid)
    sub = await sub_info(uid)

    if uid == ADMIN_ID or (u and u["plan"] != "none" and u["plan_end"]):
        await update.message.reply_text(
            f"📋 <b>اشتراكك</b>\n{'━'*28}\n\n{sub}\n",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💳 تجديد / ترقية ⭐", callback_data="menu_buy")
            ]])
        )
    else:
        await update.message.reply_text(
            "❌ <b>لا اشتراك نشط.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💳 اشترِ الآن ⭐", callback_data="menu_buy")
            ]])
        )

@sub_only
async def cmd_custom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if len(args) < 3:
        return await update.message.reply_text(
            "📝 <b>الاستخدام:</b>\n<code>/custom [طول] [عدد] [نوع]</code>\n\n"
            "أنواع: <code>alpha</code> <code>digits</code> <code>mixed</code>\n"
            "مثال: <code>/custom 4 100 alpha</code>",
            parse_mode=ParseMode.HTML
        )
    try:
        length = int(args[0])
        count  = int(args[1])
        mode   = args[2].lower()
    except ValueError:
        return await update.message.reply_text("❌ قيم غير صالحة.")

    if length not in (3, 4, 5):
        return await update.message.reply_text("❌ الطول يجب أن يكون 3 أو 4 أو 5.")
    if mode not in ("alpha", "digits", "mixed"):
        return await update.message.reply_text("❌ النوع: alpha / digits / mixed")
    count = max(10, min(count, 500))

    if engine.user_active(update.effective_user.id):
        return await update.message.reply_text("⚠️ لديك صيد نشط. /stop")

    await update.message.reply_text(
        f"🚀 <b>انطلق!</b> {length} أحرف × {count} يوزر — نوع: {mode}",
        parse_mode=ParseMode.HTML
    )
    asyncio.create_task(
        engine.start(update.effective_user.id, length, count, mode, ctx, update.effective_chat.id)
    )

@sub_only
async def cmd_prefix(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 4:
        return await update.message.reply_text(
            "📝 <code>/prefix [طول] [عدد] [نوع] [بادئة]</code>",
            parse_mode=ParseMode.HTML
        )
    try:
        length = int(ctx.args[0])
        count  = int(ctx.args[1])
        mode   = ctx.args[2].lower()
        prefix = ctx.args[3].lower()
    except (ValueError, IndexError):
        return await update.message.reply_text("❌ قيم غير صالحة.")

    if length not in (3,4,5) or mode not in ("alpha","digits","mixed"):
        return await update.message.reply_text("❌ طول: 3-5 | نوع: alpha/digits/mixed")
    count = max(10, min(count, 500))

    if engine.user_active(update.effective_user.id):
        return await update.message.reply_text("⚠️ لديك صيد نشط. /stop")

    await update.message.reply_text(
        f"🚀 صيد بالبادئة <code>{prefix}</code>", parse_mode=ParseMode.HTML
    )
    asyncio.create_task(
        engine.start(update.effective_user.id, length, count, mode, ctx, update.effective_chat.id, prefix=prefix)
    )

@sub_only
async def cmd_suffix(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 4:
        return await update.message.reply_text(
            "📝 <code>/suffix [طول] [عدد] [نوع] [لاحقة]</code>",
            parse_mode=ParseMode.HTML
        )
    try:
        length = int(ctx.args[0])
        count  = int(ctx.args[1])
        mode   = ctx.args[2].lower()
        suffix = ctx.args[3].lower()
    except (ValueError, IndexError):
        return await update.message.reply_text("❌ قيم غير صالحة.")

    if length not in (3,4,5) or mode not in ("alpha","digits","mixed"):
        return await update.message.reply_text("❌ طول: 3-5 | نوع: alpha/digits/mixed")
    count = max(10, min(count, 500))

    if engine.user_active(update.effective_user.id):
        return await update.message.reply_text("⚠️ لديك صيد نشط. /stop")

    await update.message.reply_text(
        f"🚀 صيد باللاحقة <code>{suffix}</code>", parse_mode=ParseMode.HTML
    )
    asyncio.create_task(
        engine.start(update.effective_user.id, length, count, mode, ctx, update.effective_chat.id, suffix=suffix)
    )

# ═══════════════════════════════════C��══════════════════════════════════
#  🔐 ADMIN COMMANDS
# ══════════════════════════════════════════════════════════════════════

@admin_only
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await show_admin_panel(update.message, ctx)

async def show_admin_panel(msg_or_query, ctx, edit=False):
    tu   = await db.val("SELECT COUNT(*) FROM users")
    ta   = await db.val("SELECT COUNT(*) FROM users WHERE plan!='none' AND plan_end>?", (datetime.now().isoformat(),))
    tb   = await db.val("SELECT COUNT(*) FROM users WHERE is_banned=1")
    tf   = await db.val("SELECT COUNT(*) FROM found_names")
    ts   = await db.val("SELECT COALESCE(SUM(stars),0) FROM payments")
    ac   = sum(1 for h in engine.active.values() if h["status"] == "running")
    tc   = await db.val("SELECT COUNT(*) FROM cache")

    txt = (
        f"🔐 <b>لوحة الإدارة</b>\n{'━'*32}\n"
        f"👥 المستخدمين: <b>{tu}</b>\n"
        f"✅ اشتراكات نشطة: <b>{ta}</b>\n"
        f"🚫 محظورين: <b>{tb}</b>\n"
        f"💎 يوزرات مصيدة: <b>{tf}</b>\n"
        f"🔍 كاش: <b>{tc}</b>\n"
        f"🔄 عمليات نشطة: <b>{ac}</b>\n"
        f"⭐ إجمالي النجوم: <b>{ts}</b>\n"
        f"{'━'*32}\n"
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    kb = [
        [InlineKeyboardButton("👥 المستخدمون",    callback_data="adm_users"),
         InlineKeyboardButton("💳 الاشتراكات",   callback_data="adm_subs")],
        [InlineKeyboardButton("📊 الإحصائيات",   callback_data="adm_stats"),
         InlineKeyboardButton("💰 المدفوعات",    callback_data="adm_pays")],
        [InlineKeyboardButton("📢 بث رسالة",     callback_data="adm_bc_info"),
         InlineKeyboardButton("📋 السجلات",      callback_data="adm_logs")],
        [InlineKeyboardButton("💎 كل المصيدة",   callback_data="adm_found"),
         InlineKeyboardButton("🗄️ الكاش",        callback_data="adm_cache")],
        [InlineKeyboardButton("🎯 الصيد النشط",  callback_data="adm_active_h"),
         InlineKeyboardButton("🛑 إيقاف الكل",   callback_data="adm_stopall")],
        [InlineKeyboardButton("✅ تفعيل مستخدم", callback_data="adm_act_info"),
         InlineKeyboardButton("🚫 حظر مستخدم",  callback_data="adm_ban_info")],
        [InlineKeyboardButton("♾️ تفعيل نجوم",  callback_data="adm_stars_info"),
         InlineKeyboardButton("🔄 نسخة احتياطية",callback_data="adm_backup")],
    ]
    mkp = InlineKeyboardMarkup(kb)
    if edit:
        await msg_or_query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=mkp)
    else:
        await msg_or_query.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=mkp)

@admin_only
async def cmd_activate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /activate [user_id] [plan]
    Plans: trial weekly monthly pro yearly forever custom:N
    """
    if len(ctx.args) < 2:
        return await update.message.reply_text(
            "📝 <b>تفعيل اشتراك:</b>\n"
            "<code>/activate [user_id] [plan]</code>\n\n"
            "الخطط: trial weekly monthly pro yearly forever custom:N",
            parse_mode=ParseMode.HTML
        )
    try:
        tid = int(ctx.args[0])
    except ValueError:
        return await update.message.reply_text("❌ آيدي غير صالح.")

    plan_key = ctx.args[1].lower()

    if plan_key.startswith("custom:"):
        try:
            days = int(plan_key.split(":")[1])
            plan_key = "custom"
            plan_info = {"days": days, "emoji": "📦", "name": f"مخصص {days} يوم", "desc": f"{days} يوم"}
        except Exception:
            return await update.message.reply_text("❌ صيغة custom:N — مثال: custom:15")
    elif plan_key in PLANS:
        plan_info = PLANS[plan_key]
        days      = plan_info["days"]
    else:
        return await update.message.reply_text(
            f"❌ خطة غير معروفة.\nالمتاحة: {', '.join(PLANS.keys())} custom:N"
        )

    new_end = (datetime.now() + timedelta(days=days)).isoformat()
    ex = await db.one("SELECT uid FROM users WHERE uid=?", (tid,))
    if ex:
        await db.run(
            "UPDATE users SET plan=?,plan_end=?,notified_exp=0 WHERE uid=?",
            (plan_key, new_end, tid)
        )
    else:
        await db.run(
            "INSERT INTO users (uid,plan,plan_end) VALUES (?,?,?)",
            (tid, plan_key, new_end)
        )
    await db.run(
        "INSERT INTO payments (uid,action,plan,days,by_admin) VALUES (?,?,?,?,?)",
        (tid, "admin_activate", plan_key, days, ADMIN_ID)
    )
    await db.run(
        "INSERT INTO adm_log (admin,action,detail) VALUES (?,?,?)",
        (ADMIN_ID, "activate", f"{tid} → {plan_key} {days}d")
    )

    await update.message.reply_text(
        f"✅ تم تفعيل <code>{tid}</code>\n"
        f"📦 {plan_info['name']}\n"
        f"⏰ ينتهي: {new_end[:10]}",
        parse_mode=ParseMode.HTML
    )
    try:
        await ctx.bot.send_message(
            tid,
            f"✅ <b>تم تفعيل اشتراكك!</b>\n\n"
            f"📦 {plan_info['name']}\n"
            f"📅 {plan_info['desc']}\n"
            f"⏰ ينتهي: {new_end[:10]}\n\n"
            f"ابدأ الصيد الآن! /hunt",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

@admin_only
async def cmd_deactivate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("📝 /deactivate [user_id]")
    try:
        tid = int(ctx.args[0])
    except ValueError:
        return await update.message.reply_text("❌ آيدي غير صالح.")

    await db.run("UPDATE users SET plan='none',plan_end=NULL WHERE uid=?", (tid,))
    await update.message.reply_text(f"✅ تم إلغاء اشتراك <code>{tid}</code>", parse_mode=ParseMode.HTML)

@admin_only
async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("📝 /ban [user_id] [سبب اختياري]")
    try:
        tid = int(ctx.args[0])
    except ValueError:
        return await update.message.reply_text("❌ آيدي غير صالح.")

    reason = " ".join(ctx.args[1:]) if len(ctx.args) > 1 else "مخالفة الشروط"
    await db.run("UPDATE users SET is_banned=1,ban_reason=? WHERE uid=?", (reason, tid))
    engine.stop_user(tid)
    await db.run(
        "INSERT INTO adm_log (admin,action,detail) VALUES (?,?,?)",
        (ADMIN_ID, "ban", f"{tid} — {reason}")
    )
    await update.message.reply_text(
        f"🚫 تم حظر <code>{tid}</code>\nالسبب: {reason}",
        parse_mode=ParseMode.HTML
    )

@admin_only
async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("📝 /unban [user_id]")
    try:
        tid = int(ctx.args[0])
    except ValueError:
        return await update.message.reply_text("❌ آيدي غير صالح.")

    await db.run("UPDATE users SET is_banned=0,ban_reason=NULL WHERE uid=?", (tid,))
    await update.message.reply_text(f"✅ فُكَّ حظر <code>{tid}</code>", parse_mode=ParseMode.HTML)

@admin_only
async def cmd_extend(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        return await update.message.reply_text("📝 /extend [user_id] [أيام]")
    try:
        tid  = int(ctx.args[0])
        days = int(ctx.args[1])
    except ValueError:
        return await update.message.reply_text("❌ قيم غير صالحة.")

    u = await db.one("SELECT plan_end FROM users WHERE uid=?", (tid,))
    if not u:
        return await update.message.reply_text("❌ المستخدم غير موجود.")

    try:
        base = max(datetime.fromisoformat(u["plan_end"]) if u["plan_end"] else datetime.now(), datetime.now())
    except Exception:
        base = datetime.now()

    new_end = (base + timedelta(days=days)).isoformat()
    await db.run("UPDATE users SET plan_end=?,notified_exp=0 WHERE uid=?", (new_end, tid))
    await update.message.reply_text(
        f"✅ تم تمديد <code>{tid}</code> بـ {days} يوم\nينتهي: {new_end[:10]}",
        parse_mode=ParseMode.HTML
    )
    try:
        await ctx.bot.send_message(
            tid,
            f"🎁 تم تمديد اشتراكك {days} يوم إضافية!\n⏰ ينتهي: {new_end[:10]}",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

@admin_only
async def cmd_vip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("📝 /vip [user_id]")
    try:
        tid = int(ctx.args[0])
    except ValueError:
        return await update.message.reply_text("❌ آيدي غير صالح.")

    u = await db.one("SELECT is_vip FROM users WHERE uid=?", (tid,))
    if not u:
        return await update.message.reply_text("❌ المستخدم غير موجود.")

    nv = 0 if u["is_vip"] else 1
    await db.run("UPDATE users SET is_vip=? WHERE uid=?", (nv, tid))
    await update.message.reply_text(
        f"⭐ {'تفعيل' if nv else 'إلغاء'} VIP لـ <code>{tid}</code>",
        parse_mode=ParseMode.HTML
    )

@admin_only
async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("📝 /broadcast [رسالة]")

    text  = " ".join(ctx.args)
    users = await db.all("SELECT uid FROM users WHERE is_banned=0")
    ok = fail = 0

    for u in users:
        try:
            await ctx.bot.send_message(
                u["uid"],
                f"📢 <b>رسالة من الإدارة</b>\n{'━'*28}\n\n{text}\n\n{'━'*28}\n👨‍💻 {DEV_TAG}",
                parse_mode=ParseMode.HTML
            )
            ok += 1
            await asyncio.sleep(0.07)
        except Exception:
            fail += 1

    await db.run(
        "INSERT INTO broadcasts (msg,target,sent,failed) VALUES (?,?,?,?)",
        (text, "all", ok, fail)
    )
    await update.message.reply_text(
        f"📢 <b>تم البث للجميع</b>\n✅ أُرسل: {ok}\n❌ فشل: {fail}",
        parse_mode=ParseMode.HTML
    )

@admin_only
async def cmd_broadcast_active(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("📝 /broadcast_active [رسالة]")

    text  = " ".join(ctx.args)
    users = await db.all(
        "SELECT uid FROM users WHERE plan!='none' AND plan_end>? AND is_banned=0",
        (datetime.now().isoformat(),)
    )
    ok = fail = 0
    for u in users:
        try:
            await ctx.bot.send_message(
                u["uid"],
                f"📢 <b>للمشتركين</b>\n{'━'*28}\n\n{text}",
                parse_mode=ParseMode.HTML
            )
            ok += 1
            await asyncio.sleep(0.07)
        except Exception:
            fail += 1

    await update.message.reply_text(f"📢 المشتركون: ✅ {ok} | ❌ {fail}")

@admin_only
async def cmd_userinfo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("📝 /userinfo [user_id]")
    try:
        tid = int(ctx.args[0])
    except ValueError:
        return await update.message.reply_text("❌ آيدي غير صالح.")

    u = await db.one("SELECT * FROM users WHERE uid=?", (tid,))
    if not u:
        return await update.message.reply_text("❌ المستخدم غير موجود في قاعدة البيانات.")

    tf  = await db.val("SELECT COUNT(*) FROM found_names WHERE found_by=?", (tid,))
    ts  = await db.val("SELECT COALESCE(SUM(stars),0) FROM payments WHERE uid=?", (tid,))
    th  = await db.val("SELECT COUNT(*) FROM sessions WHERE uid=?", (tid,))
    sub = await sub_info(tid)

    txt = (
        f"👤 <b>معلومات المستخدم</b>\n{'━'*30}\n"
        f"🆔 <code>{u['uid']}</code>\n"
        f"📛 @{u['uname'] or '—'}\n"
        f"📝 {(u['fname'] or '')} {(u['lname'] or '')}\n"
        f"{'━'*30}\n"
        f"📋 الاشتراك: {sub}\n"
        f"📅 ينتهي: {u['plan_end'] or '—'}\n"
        f"⭐ VIP: {'نعم' if u['is_vip'] else 'لا'}\n"
        f"🚫 محظور: {'نعم — ' + (u['ban_reason'] or '') if u['is_banned'] else 'لا'}\n"
        f"{'━'*30}\n"
        f"🎯 جلسات الصيد: {th}\n"
        f"✅ يوزرات مصيدة: {tf}\n"
        f"⭐ نجوم دفعها: {ts}\n"
        f"📅 انضم: {u['joined_at'][:10]}\n"
        f"🔄 آخر نشاط: {u['last_active'][:10]}"
    )

    kb = [
        [InlineKeyboardButton("✅ تفعيل",    callback_data=f"ua_act_{tid}"),
         InlineKeyboardButton("❌ إلغاء",    callback_data=f"ua_deact_{tid}")],
        [InlineKeyboardButton("🚫 حظر",      callback_data=f"ua_ban_{tid}"),
         InlineKeyboardButton("✅ فك الحظر", callback_data=f"ua_unban_{tid}")],
        [InlineKeyboardButton("⭐ VIP",      callback_data=f"ua_vip_{tid}"),
         InlineKeyboardButton("🔙 رجوع",    callback_data="adm_panel")],
    ]
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

@admin_only
async def cmd_allstats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tu   = await db.val("SELECT COUNT(*) FROM users")
    ta   = await db.val("SELECT COUNT(*) FROM users WHERE plan!='none' AND plan_end>?", (datetime.now().isoformat(),))
    tb   = await db.val("SELECT COUNT(*) FROM users WHERE is_banned=1")
    tf   = await db.val("SELECT COUNT(*) FROM found_names")
    tr   = await db.val("SELECT COUNT(*) FROM found_names WHERE is_rare=1")
    tc   = await db.val("SELECT COUNT(*) FROM cache")
    th   = await db.val("SELECT COUNT(*) FROM sessions")
    ts   = await db.val("SELECT COALESCE(SUM(stars),0) FROM payments")
    t3   = await db.val("SELECT COUNT(*) FROM found_names WHERE len=3")
    t4   = await db.val("SELECT COUNT(*) FROM found_names WHERE len=4")
    t5   = await db.val("SELECT COUNT(*) FROM found_names WHERE len=5")
    tp   = await db.val("SELECT COUNT(*) FROM payments WHERE action='stars_buy'")

    await update.message.reply_text(
        f"📊 <b>الإحصائيات الشاملة</b>\n{'━'*32}\n\n"
        f"<b>👥 المستخدمون:</b>\n"
        f"  الكل: {tu} | نشطون: {ta} | محظورون: {tb}\n\n"
        f"<b>💰 المالية:</b>\n"
        f"  ⭐ إجمالي النجوم: {ts}\n"
        f"  📦 عمليات الشراء: {tp}\n\n"
        f"<b>🎯 الصيد:</b>\n"
        f"  فُحص (كاش): {tc}\n"
        f"  مصيدة: {tf} | نادرة: {tr}\n"
        f"  جلسات: {th}\n\n"
        f"<b>📏 التوزيع:</b>\n"
        f"  3️⃣ ثلاثية: {t3}\n"
        f"  4️⃣ رباعية: {t4}\n"
        f"  5️⃣ خماسية: {t5}",
        parse_mode=ParseMode.HTML
    )

@admin_only
async def cmd_users(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    page = int(ctx.args[0]) if ctx.args else 1
    limit, offset = 20, (page - 1) * 20
    rows  = await db.all(
        "SELECT uid,uname,plan,is_banned FROM users ORDER BY joined_at DESC LIMIT ? OFFSET ?",
        (limit, offset)
    )
    total = await db.val("SELECT COUNT(*) FROM users")
    if not rows:
        return await update.message.reply_text("📭 لا يوجد مستخدمين.")

    txt = f"👥 <b>المستخدمون</b> (صفحة {page} — {total} إجمالي)\n\n"
    for r in rows:
        s = "✅" if r["plan"] != "none" else "❌"
        b = "🚫" if r["is_banned"] else ""
        txt += f"{s}{b} <code>{r['uid']}</code> @{r['uname'] or '—'} [{r['plan']}]\n"

    kb = []
    if page > 1:
        kb.append(InlineKeyboardButton(f"◀ {page-1}", callback_data=f"adm_up_{page-1}"))
    if total > page * limit:
        kb.append(InlineKeyboardButton(f"{page+1} ▶", callback_data=f"adm_up_{page+1}"))

    await update.message.reply_text(
        txt, parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([kb]) if kb else None
    )

@admin_only
async def cmd_stopall(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    engine.stop_all()
    await update.message.reply_text("🛑 تم إيقاف جميع عمليات الصيد.")

@admin_only
async def cmd_foundall(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = await db.all("SELECT * FROM found_names ORDER BY rarity DESC LIMIT 50")
    if not rows:
        return await update.message.reply_text("📭 لا توجد يوزرات مصيدة.")

    txt = f"💎 <b>جميع المصيدة</b> ({len(rows)})\n{'━'*28}\n\n"
    for r in rows:
        em = "💎" if r["is_rare"] else "✅"
        txt += f"{em} <code>@{r['username']}</code> — {r['len']}ح — {r['rarity']}% — {r['found_at'][:10]}\n"
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)

@admin_only
async def cmd_logs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = await db.all("SELECT * FROM adm_log ORDER BY at DESC LIMIT 25")
    txt  = f"📋 <b>سجل إجراءات الإدارة</b>\n\n"
    txt += "\n".join(f"🔹 {r['action']} — {r['detail']} — {r['at'][:16]}" for r in rows) if rows else "لا توجد سجلات."
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)

@admin_only
async def cmd_backup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"manual_{ts}.db"
    dst  = os.path.join(BCK_DIR, name)
    shutil.copy2(DB_PATH, dst)
    await update.message.reply_text(f"✅ نسخة احتياطية:\n<code>{name}</code>", parse_mode=ParseMode.HTML)

@admin_only
async def cmd_payments(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = await db.all("SELECT * FROM payments ORDER BY created DESC LIMIT 30")
    if not rows:
        return await update.message.reply_text("📭 لا توجد مدفوعات.")

    txt = f"💰 <b>سجل المدفوعات</b>\n{'━'*30}\n\n"
    for r in rows:
        stars = f"⭐{r['stars']}" if r["stars"] else "مجاني"
        txt  += f"<code>{r['uid']}</code> — {r['action']} — {r['plan']} — {stars} — {r['created'][:10]}\n"
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)

@admin_only
async def cmd_clearcache(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    old = datetime.now() - timedelta(hours=CACHE_HOURS)
    c   = await db.run("DELETE FROM cache WHERE checked_at<?", (old.isoformat(),))
    await update.message.reply_text(f"🗑️ تم حذف الكاش القديم (أكثر من {CACHE_HOURS} ساعة).")

@admin_only
async def cmd_addstars(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """تفعيل دائم للمدير وأي مستخدم بنجوم وهمية للتجربة"""
    if len(ctx.args) < 2:
        return await update.message.reply_text("📝 /addstars [user_id] [نجوم]")
    try:
        tid   = int(ctx.args[0])
        stars = int(ctx.args[1])
    except ValueError:
        return await update.message.reply_text("❌ قيم غير صالحة.")

    await update.message.reply_text(
        f"ℹ️ <code>/addstars</code> للتجربة فقط.\n"
        f"استخدم /activate {tid} monthly لتفعيل حقيقي.",
        parse_mode=ParseMode.HTML
    )

# ══════════════════════════════════════════════════════════════════════
#  🖱️ CALLBACKS (Inline Keyboard)
# ══════════════════════════════════════════════════════════════════════

async def handle_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    await q.answer()
    data = q.data
    uid  = q.from_user.id
    cid  = q.message.chat_id

    def adm_kb():
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة الإدارة", callback_data="adm_panel")]])
    def back_kb():
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الرئيسية", callback_data="menu_back")]])

    async def need_sub():
        if uid == ADMIN_ID:
            return True
        if not await has_sub(uid):
            await q.edit_message_text(
                "⛔ <b>تحتاج اشتراكاً لهذه الميزة.</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💳 اشترِ الآن ⭐", callback_data="menu_buy")
                ]])
            )
            return False
        u = await get_user(uid)
        if u and u["is_banned"]:
            await q.edit_message_text(f"🚫 محظور. السبب: {u['ban_reason'] or '—'}")
            return False
        return True

    # ═══ Main menu ═══════════════════════════════════════════════════

    if data == "menu_back":
        u   = update.effective_user
        sub = await sub_info(uid)
        kb  = [
            [InlineKeyboardButton("🎯 ابدأ الصيد",       callback_data="menu_hunt"),
             InlineKeyboardButton("💳 اشترِ اشتراكاً",  callback_data="menu_buy")],
            [InlineKeyboardButton("📊 إحصائياتي",        callback_data="menu_stats"),
             InlineKeyboardButton("💎 يوزراتي",         callback_data="menu_found")],
            [InlineKeyboardButton("📋 اشتراكي",         callback_data="menu_sub"),
             InlineKeyboardButton("❓ مساعدة",          callback_data="menu_help")],
        ]
        if uid == ADMIN_ID:
            kb.append([InlineKeyboardButton("🔐 لوحة الإدارة ◀", callback_data="adm_panel")])
        await q.edit_message_text(
            f"🏠 <b>القائمة الرئيسية</b>\n📋 اشتراكك: {sub}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif data == "menu_buy":
        kb = []
        for k, p in PLANS.items():
            kb.append([InlineKeyboardButton(
                f"{p['emoji']} {p['name']} — {p['stars']} ⭐ ({p['desc']})",
                callback_data=f"buy_{k}"
            )])
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu_back")])
        await q.edit_message_text(
            f"💳 <b>اختر خطة الاشتراك</b>\n{'━'*30}\n\n"
            f"⭐ الدفع بنجوم تيليجرام الآمنة\n"
            f"✅ تفعيل فوري — 🔄 يمدّد تلقائياً",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif data.startswith("buy_"):
        plan_key = data[4:]
        if plan_key not in PLANS:
            return
        await q.message.delete()
        await send_invoice(ctx, cid, plan_key)

    elif data == "menu_hunt":
        if not await need_sub():
            return
        if engine.user_active(uid):
            await q.edit_message_text(
                "⚠️ لديك صيد نشط!\nاستخدم /stop لإيقافه أولاً.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="menu_back")]])
            )
            return
        kb = [
            [InlineKeyboardButton("3️⃣ ثلاثية 💎", callback_data="ht_3_alpha"),
             InlineKeyboardButton("4️⃣ رباعية ⭐", callback_data="ht_4_alpha"),
             InlineKeyboardButton("5️⃣ خماسية ✅", callback_data="ht_5_alpha")],
            [InlineKeyboardButton("🔥 توربو 3",    callback_data="turbo_3"),
             InlineKeyboardButton("🔥 توربو 4",    callback_data="turbo_4"),
             InlineKeyboardButton("🔥 توربو 5",    callback_data="turbo_5")],
            [InlineKeyboardButton("💎 نادرة 3",    callback_data="ultra_3"),
             InlineKeyboardButton("💎 نادرة 4",    callback_data="ultra_4"),
             InlineKeyboardButton("🎲 مختلط 4",    callback_data="ht_4_mixed")],
            [InlineKeyboardButton("⚙️ مخصص",       callback_data="menu_custom"),
             InlineKeyboardButton("🔙 رجوع",       callback_data="menu_back")],
        ]
        await q.edit_message_text(
            "🎯 <b>اختر نوع الصيد:</b>\n\n"
            "💎 ثلاثية — نادرة جداً (3 أحرف)\n"
            "⭐ رباعية — نادرة (4 أحرف)\n"
            "✅ خماسية — متاحة (5 أحرف)\n\n"
            "🔥 توربو = 250 يوزر بسرعة\n"
            "💎 نادرة = أحرف فقط (أعلى قيمة)",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif data.startswith("ht_"):
        if not await need_sub():
            return
        _, length, mode = data.split("_", 2)
        length = int(length)
        kb = [
            [InlineKeyboardButton("30",  callback_data=f"hs_{length}_{mode}_30"),
             InlineKeyboardButton("60",  callback_data=f"hs_{length}_{mode}_60")],
            [InlineKeyboardButton("100", callback_data=f"hs_{length}_{mode}_100"),
             InlineKeyboardButton("200", callback_data=f"hs_{length}_{mode}_200")],
            [InlineKeyboardButton("350", callback_data=f"hs_{length}_{mode}_350"),
             InlineKeyboardButton("500", callback_data=f"hs_{length}_{mode}_500")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="menu_hunt")],
        ]
        await q.edit_message_text(
            f"📊 <b>كم يوزر تريد فحصه؟</b>\n📏 {length} أحرف | 🔤 {mode}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif data.startswith("hs_"):
        if not await need_sub():
            return
        parts  = data.split("_")
        length = int(parts[1])
        mode   = parts[2]
        count  = int(parts[3])
        await q.edit_message_text(
            f"🚀 <b>انطلق!</b>\n📏 {length} أحرف | 🔤 {mode} | 📊 {count} يوزر",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(engine.start(uid, length, count, mode, ctx, cid))

    elif data.startswith("turbo_"):
        if not await need_sub():
            return
        length = int(data[-1])
        await q.edit_message_text(
            f"🔥 <b>توربو {length} أحرف — 250 يوزر</b>\n🚀 انطلق!",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(engine.start(uid, length, 250, "mixed", ctx, cid))

    elif data.startswith("ultra_"):
        if not await need_sub():
            return
        length = int(data[-1])
        await q.edit_message_text(
            f"💎 <b>Ultra Scan {length} أحرف</b>\n🔍 نادرة فقط (أحرف لاتينية)",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(engine.start(uid, length, 150, "alpha", ctx, cid))

    elif data == "menu_custom":
        await q.edit_message_text(
            "⚙️ <b>الصيد المخصص</b>\n{'━'*28}\n\n"
            "<code>/custom [طول] [عدد] [نوع]</code>\n"
            "<code>/prefix [طول] [عدد] [نوع] [بادئة]</code>\n"
            "<code>/suffix [طول] [عدد] [نوع] [لاحقة]</code>\n\n"
            "مثال: <code>/custom 4 150 alpha</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="menu_hunt")]])
        )

    elif data == "menu_stats":
        u  = await get_user(uid)
        tf = await db.val("SELECT COUNT(*) FROM found_names WHERE found_by=?", (uid,))
        tr = await db.val("SELECT COUNT(*) FROM found_names WHERE found_by=? AND is_rare=1", (uid,))
        ts = await db.val("SELECT COALESCE(SUM(stars),0) FROM payments WHERE uid=?", (uid,))
        sub = await sub_info(uid)
        await q.edit_message_text(
            f"📊 <b>إحصائياتك</b>\n{'━'*28}\n\n"
            f"📋 الاشتراك: {sub}\n"
            f"⭐ نجوم دفعتها: {ts}\n"
            f"{'━'*28}\n"
            f"🎯 جلسات الصيد: {u['total_hunts'] if u else 0}\n"
            f"✅ مصيدة: {tf}\n"
            f"💎 نادرة: {tr}",
            parse_mode=ParseMode.HTML,
            reply_markup=back_kb()
        )

    elif data == "menu_found":
        rows = await db.all("SELECT * FROM found_names WHERE found_by=? ORDER BY rarity DESC LIMIT 30", (uid,))
        if not rows:
            txt = "📭 لم تصطد أي يوزرات بعد.\nابدأ /hunt"
        else:
            txt = f"💎 <b>يوزراتك</b> ({len(rows)})\n\n"
            for r in rows:
                em = "💎" if r["is_rare"] else "✅"
                txt += f"{em} <code>@{r['username']}</code> — {r['len']}ح — {r['rarity']}%\n"
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=back_kb())

    elif data == "menu_sub":
        sub = await sub_info(uid)
        u   = await get_user(uid)
        ex  = ""
        if u and u["plan_end"]:
            ex = f"\n📅 ينتهي: {u['plan_end'][:10]}"
        await q.edit_message_text(
            f"📋 <b>اشتراكك</b>\n\n{sub}{ex}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 تجديد / ترقية ⭐", callback_data="menu_buy")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="menu_back")],
            ])
        )

    elif data == "menu_help":
        await q.edit_message_text(
            f"📖 <b>المساعدة</b>\n{'━'*28}\n\n"
            f"/hunt — بدء الصيد\n"
            f"/check — فحص يوزر\n"
            f"/stop — إيقاف الصيد\n"
            f"/stats — إحصائياتي\n"
            f"/found — يوزراتي\n"
            f"/sub — اشتراكي\n"
            f"/buy — شراء اشتراك\n\n"
            f"👨‍💻 {DEV_TAG}",
            parse_mode=ParseMode.HTML,
            reply_markup=back_kb()
        )

    # ═══ Admin panel ════════════════════════════════════════════════

    elif data == "adm_panel" and uid == ADMIN_ID:
        await show_admin_panel(q, ctx, edit=True)

    elif data == "adm_users" and uid == ADMIN_ID:
        rows  = await db.all("SELECT uid,uname,plan,is_banned FROM users ORDER BY joined_at DESC LIMIT 25")
        total = await db.val("SELECT COUNT(*) FROM users")
        txt   = f"👥 <b>المستخدمون</b> ({total} إجمالي)\n\n"
        for r in rows:
            s = "✅" if r["plan"] != "none" else "❌"
            b = "🚫" if r["is_banned"] else ""
            txt += f"{s}{b} <code>{r['uid']}</code> @{r['uname'] or '—'} [{r['plan']}]\n"
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=adm_kb())

    elif data == "adm_subs" and uid == ADMIN_ID:
        rows = await db.all(
            "SELECT uid,uname,plan,plan_end FROM users WHERE plan!='none' ORDER BY plan_end DESC"
        )
        txt = f"💳 <b>الاشتراكات النشطة</b> ({len(rows)})\n\n"
        now = datetime.now().isoformat()
        for r in rows:
            active = "✅" if r["plan_end"] and r["plan_end"] > now else "❌"
            txt += f"{active} <code>{r['uid']}</code> — {r['plan']} — {(r['plan_end'] or '—')[:10]}\n"
        if not rows:
            txt += "لا توجد اشتراكات."
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=adm_kb())

    elif data == "adm_stats" and uid == ADMIN_ID:
        tu  = await db.val("SELECT COUNT(*) FROM users")
        ta  = await db.val("SELECT COUNT(*) FROM users WHERE plan!='none' AND plan_end>?", (datetime.now().isoformat(),))
        tf  = await db.val("SELECT COUNT(*) FROM found_names")
        ts  = await db.val("SELECT COALESCE(SUM(stars),0) FROM payments")
        tc  = await db.val("SELECT COUNT(*) FROM cache")
        ac  = sum(1 for h in engine.active.values() if h["status"] == "running")
        await q.edit_message_text(
            f"📊 <b>الإحصائيات</b>\n\n"
            f"👥 {tu} مستخدم | ✅ {ta} نشط\n"
            f"💎 {tf} مصيدة\n"
            f"🔍 {tc} في الكاش\n"
            f"🔄 {ac} عملية نشطة\n"
            f"⭐ {ts} نجمة",
            parse_mode=ParseMode.HTML, reply_markup=adm_kb()
        )

    elif data == "adm_pays" and uid == ADMIN_ID:
        rows = await db.all("SELECT * FROM payments ORDER BY created DESC LIMIT 20")
        txt  = f"💰 <b>المدفوعات</b>\n\n"
        ts   = await db.val("SELECT COALESCE(SUM(stars),0) FROM payments")
        txt += f"إجمالي النجوم: ⭐ {ts}\n{'━'*28}\n\n"
        for r in rows:
            stars = f"⭐{r['stars']}" if r["stars"] else "مجاني"
            txt  += f"<code>{r['uid']}</code> {r['action']} {r['plan']} {stars} {r['created'][:10]}\n"
        await q.edit_message_text(txt or "لا توجد.", parse_mode=ParseMode.HTML, reply_markup=adm_kb())

    elif data == "adm_bc_info" and uid == ADMIN_ID:
        await q.edit_message_text(
            "📢 <b>البث</b>\n\n"
            "<code>/broadcast [رسالة]</code> — للجميع\n"
            "<code>/broadcast_active [رسالة]</code> — للمشتركين فقط",
            parse_mode=ParseMode.HTML, reply_markup=adm_kb()
        )

    elif data == "adm_logs" and uid == ADMIN_ID:
        rows = await db.all("SELECT * FROM adm_log ORDER BY at DESC LIMIT 15")
        txt  = f"📋 <b>سجل الإدارة</b>\n\n"
        txt += "\n".join(f"🔹 {r['action']} — {r['detail']} — {r['at'][:16]}" for r in rows) or "لا توجد."
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=adm_kb())

    elif data == "adm_found" and uid == ADMIN_ID:
        rows = await db.all("SELECT * FROM found_names ORDER BY rarity DESC LIMIT 40")
        txt  = f"💎 <b>جميع المصيدة</b> ({len(rows)})\n\n"
        for r in rows:
            em = "💎" if r["is_rare"] else "✅"
            txt += f"{em} <code>@{r['username']}</code> — {r['len']}ح — {r['rarity']}%\n"
        await q.edit_message_text(txt or "📭 لا توجد.", parse_mode=ParseMode.HTML, reply_markup=adm_kb())

    elif data == "adm_cache" and uid == ADMIN_ID:
        total   = await db.val("SELECT COUNT(*) FROM cache")
        avail   = await db.val("SELECT COUNT(*) FROM cache WHERE status='available'")
        taken   = await db.val("SELECT COUNT(*) FROM cache WHERE status='taken'")
        old_dt  = (datetime.now() - timedelta(hours=CACHE_HOURS)).isoformat()
        old_cnt = await db.val("SELECT COUNT(*) FROM cache WHERE checked_at<?", (old_dt,))
        await q.edit_message_text(
            f"🗄️ <b>الكاش</b>\n\n"
            f"📦 الكل: {total}\n"
            f"✅ متاح: {avail}\n❌ محجوز: {taken}\n"
            f"🕰️ قديم: {old_cnt}\n\n"
            f"استخدم /clearcache لحذف القديم",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ حذف القديم", callback_data="adm_clear_cache")],
                [InlineKeyboardButton("🔙 رجوع",       callback_data="adm_panel")],
            ])
        )

    elif data == "adm_clear_cache" and uid == ADMIN_ID:
        old = (datetime.now() - timedelta(hours=CACHE_HOURS)).isoformat()
        await db.run("DELETE FROM cache WHERE checked_at<?", (old,))
        await q.edit_message_text("✅ تم حذف الكاش القديم.", reply_markup=adm_kb())

    elif data == "adm_active_h" and uid == ADMIN_ID:
        running = [(hid, h) for hid, h in engine.active.items() if h["status"] == "running"]
        txt = f"🔄 <b>عمليات الصيد النشطة</b> ({len(running)})\n\n"
        for hid, h in running:
            txt += f"🔹 <code>{hid}</code> — {h['uid']} — {h['checked']}/{h['total']} — وجد {h['found']}\n"
        await q.edit_message_text(txt or "لا توجد عمليات نشطة.", parse_mode=ParseMode.HTML, reply_markup=adm_kb())

    elif data == "adm_stopall" and uid == ADMIN_ID:
        engine.stop_all()
        await q.edit_message_text("🛑 تم إيقاف جميع العمليات.", reply_markup=adm_kb())

    elif data == "adm_act_info" and uid == ADMIN_ID:
        plans_txt = "\n".join(f"  • {k}" for k in PLANS.keys())
        await q.edit_message_text(
            f"✅ <b>تفعيل اشتراك</b>\n\n"
            f"<code>/activate [user_id] [plan]</code>\n\n"
            f"الخطط المتاحة:\n{plans_txt}\n  • custom:N (N = عدد الأيام)\n\n"
            f"مثال: <code>/activate 123456 monthly</code>",
            parse_mode=ParseMode.HTML, reply_markup=adm_kb()
        )

    elif data == "adm_ban_info" and uid == ADMIN_ID:
        await q.edit_message_text(
            "🚫 <b>حظر / فك حظر</b>\n\n"
            "<code>/ban [user_id] [سبب]</code>\n"
            "<code>/unban [user_id]</code>\n"
            "<code>/userinfo [user_id]</code>",
            parse_mode=ParseMode.HTML, reply_markup=adm_kb()
        )

    elif data == "adm_stars_info" and uid == ADMIN_ID:
        await q.edit_message_text(
            "⭐ <b>إدارة النجوم</b>\n\n"
            "لمنح اشتراك مجاني: /activate\n"
            "لعرض المدفوعات: /payments\n"
            "لإلغاء اشتراك: /deactivate",
            parse_mode=ParseMode.HTML, reply_markup=adm_kb()
        )

    elif data == "adm_backup" and uid == ADMIN_ID:
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"manual_{ts}.db"
        shutil.copy2(DB_PATH, os.path.join(BCK_DIR, name))
        await q.edit_message_text(
            f"✅ <b>نسخة احتياطية</b>\n<code>{name}</code>",
            parse_mode=ParseMode.HTML, reply_markup=adm_kb()
        )

    elif data.startswith("adm_up_") and uid == ADMIN_ID:
        page  = int(data.split("_")[-1])
        limit = 20
        offset = (page - 1) * limit
        rows   = await db.all("SELECT uid,uname,plan,is_banned FROM users ORDER BY joined_at DESC LIMIT ? OFFSET ?", (limit, offset))
        total  = await db.val("SELECT COUNT(*) FROM users")
        txt    = f"👥 <b>المستخدمون</b> (صفحة {page} — {total} إجمالي)\n\n"
        for r in rows:
            s = "✅" if r["plan"] != "none" else "❌"
            b = "🚫" if r["is_banned"] else ""
            txt += f"{s}{b} <code>{r['uid']}</code> @{r['uname'] or '—'} [{r['plan']}]\n"
        kb_row = []
        if page > 1:
            kb_row.append(InlineKeyboardButton(f"◀ {page-1}", callback_data=f"adm_up_{page-1}"))
        if total > page * limit:
            kb_row.append(InlineKeyboardButton(f"{page+1} ▶", callback_data=f"adm_up_{page+1}"))
        kb_row2 = [InlineKeyboardButton("🔙 لوحة الإدارة", callback_data="adm_panel")]
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([kb_row, kb_row2]))

    # ═══ Inline admin user actions ═══════════════════════════════════

    elif data.startswith("ua_act_") and uid == ADMIN_ID:
        tid = data.replace("ua_act_", "")
        kb  = []
        for k, p in PLANS.items():
            kb.append([InlineKeyboardButton(
                f"{p['emoji']} {p['name']} ({p['desc']})",
                callback_data=f"do_act_{tid}_{k}"
            )])
        kb.append([InlineKeyboardButton("🔙", callback_data="adm_panel")])
        await q.edit_message_text(
            f"✅ اختر خطة لتفعيلها لـ <code>{tid}</code>:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif data.startswith("do_act_") and uid == ADMIN_ID:
        rest = data[7:]
        last_underscore = rest.rfind("_")
        tid      = int(rest[:last_underscore])
        plan_key = rest[last_underscore+1:]
        if plan_key not in PLANS:
            return
        p    = PLANS[plan_key]
        days = p["days"]
        end  = (datetime.now() + timedelta(days=days)).isoformat()
        ex   = await db.one("SELECT uid FROM users WHERE uid=?", (tid,))
        if ex:
            await db.run("UPDATE users SET plan=?,plan_end=?,notified_exp=0 WHERE uid=?", (plan_key, end, tid))
        else:
            await db.run("INSERT INTO users (uid,plan,plan_end) VALUES (?,?,?)", (tid, plan_key, end))
        try:
            await ctx.bot.send_message(
                tid,
                f"✅ <b>تم تفعيل اشتراكك!</b>\n{p['emoji']} {p['name']} — {p['desc']}\n⏰ {end[:10]}",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        await q.edit_message_text(
            f"✅ تم تفعيل <code>{tid}</code> — {p['emoji']} {p['name']}",
            parse_mode=ParseMode.HTML, reply_markup=adm_kb()
        )

    elif data.startswith("ua_deact_") and uid == ADMIN_ID:
        tid = int(data.replace("ua_deact_", ""))
        await db.run("UPDATE users SET plan='none',plan_end=NULL WHERE uid=?", (tid,))
        await q.edit_message_text(
            f"❌ تم إلغاء اشتراك <code>{tid}</code>",
            parse_mode=ParseMode.HTML, reply_markup=adm_kb()
        )

    elif data.startswith("ua_ban_") and uid == ADMIN_ID:
        tid = int(data.replace("ua_ban_", ""))
        await db.run("UPDATE users SET is_banned=1,ban_reason='قرار إداري' WHERE uid=?", (tid,))
        engine.stop_user(tid)
        await q.edit_message_text(
            f"🚫 تم حظر <code>{tid}</code>",
            parse_mode=ParseMode.HTML, reply_markup=adm_kb()
        )

    elif data.startswith("ua_unban_") and uid == ADMIN_ID:
        tid = int(data.replace("ua_unban_", ""))
        await db.run("UPDATE users SET is_banned=0,ban_reason=NULL WHERE uid=?", (tid,))
        await q.edit_message_text(
            f"✅ فُكَّ حظر <code>{tid}</code>",
            parse_mode=ParseMode.HTML, reply_markup=adm_kb()
        )

    elif data.startswith("ua_vip_") and uid == ADMIN_ID:
        tid = int(data.replace("ua_vip_", ""))
        u   = await db.one("SELECT is_vip FROM users WHERE uid=?", (tid,))
        if u:
            nv = 0 if u["is_vip"] else 1
            await db.run("UPDATE users SET is_vip=? WHERE uid=?", (nv, tid))
            await q.edit_message_text(
                f"⭐ {'✅ تفعيل' if nv else '❌ إلغاء'} VIP لـ <code>{tid}</code>",
                parse_mode=ParseMode.HTML, reply_markup=adm_kb()
            )

# ══════════════════════════════════════════════════════════════════════
#  ⏰ BACKGROUND TASKS
# ══════════════════════════════════════════════════════════════════════

async def expiry_notifier(app):
    while True:
        try:
            warn_time = (datetime.now() + timedelta(days=1)).isoformat()
            rows = await db.all(
                "SELECT uid,plan_end FROM users WHERE plan!='none' AND plan_end<=? AND plan_end>? AND notified_exp=0",
                (warn_time, datetime.now().isoformat())
            )
            for u in rows:
                try:
                    await app.bot.send_message(
                        u["uid"],
                        f"⚠️ <b>تنبيه: اشتراكك ينتهي غداً!</b>\n\n"
                        f"📅 {u['plan_end'][:10]}\n"
                        f"جدّد الآن قبل الانقطاع ⭐",
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("💳 تجديد الآن ⭐", callback_data="menu_buy")
                        ]])
                    )
                    await db.run("UPDATE users SET notified_exp=1 WHERE uid=?", (u["uid"],))
                except Exception:
                    pass

            # إلغاء المنتهية
            await db.run(
                "UPDATE users SET plan='none',notified_exp=0 WHERE plan!='none' AND plan_end<?",
                (datetime.now().isoformat(),)
            )
        except Exception as e:
            logger.error(f"Expiry notifier: {e}")
        await asyncio.sleep(1800)  # كل 30 دقيقة

async def auto_backup_task():
    while True:
        try:
            ts   = datetime.now().strftime("%Y%m%d_%H%M")
            name = f"auto_{ts}.db"
            shutil.copy2(DB_PATH, os.path.join(BCK_DIR, name))
            # احتفظ بآخر 7 نسخ
            bks = sorted(f for f in os.listdir(BCK_DIR) if f.startswith("auto_"))
            for old in bks[:-7]:
                try:
                    os.remove(os.path.join(BCK_DIR, old))
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Auto backup: {e}")
        await asyncio.sleep(21600)  # كل 6 ساعات

async def cache_cleaner():
    while True:
        try:
            old = (datetime.now() - timedelta(hours=CACHE_HOURS)).isoformat()
            await db.run("DELETE FROM cache WHERE checked_at<?", (old,))
        except Exception as e:
            logger.error(f"Cache cleaner: {e}")
        await asyncio.sleep(3600)  # كل ساعة

async def error_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    err = str(ctx.error)
    logger.error(f"Error: {err}", exc_info=ctx.error)
    if "Message is not modified" in err or "Query is too old" in err:
        return
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text("❌ حدث خطأ. حاول مجدداً أو استخدم /start")
        except Exception:
            pass

# ══════════════════════════════════════════════════════════════════════
#  🚀 STARTUP / SHUTDOWN
# ══════════════════════════════════════════════════════════════════════

async def on_start(app):
    await db.init()
    await app.bot.set_my_commands([
        BotCommand("start",           "القائمة الرئيسية"),
        BotCommand("hunt",            "بدء الصيد"),
        BotCommand("check",           "فحص يوزر محدد"),
        BotCommand("stop",            "إيقاف الصيد"),
        BotCommand("stats",           "إحصائياتي"),
        BotCommand("found",           "يوزراتي المصيدة"),
        BotCommand("sub",             "حالة اشتراكي"),
        BotCommand("buy",             "شراء اشتراك بنجوم"),
        BotCommand("custom",          "صيد مخصص"),
        BotCommand("prefix",          "صيد ببادئة"),
        BotCommand("suffix",          "صيد بلاحقة"),
        BotCommand("help",            "المساعدة"),
    ])
    asyncio.create_task(expiry_notifier(app))
    asyncio.create_task(auto_backup_task())
    asyncio.create_task(cache_cleaner())

    logger.info(f"🚀 {BOT_NAME} v{BOT_VER} — Admin: {ADMIN_ID}")

    try:
        await app.bot.send_message(
            ADMIN_ID,
            f"🟢 <b>{BOT_NAME}</b> يعمل!\n"
            f"{'━'*30}\n"
            f"📦 الإصدار: {BOT_VER}\n"
            f"🌐 Keep-Alive: port 5000\n"
            f"💳 نجوم تيليجرام: ✅ مفعّل\n"
            f"🔍 تحقق مزدوج: {VERIFY_TIMES}×\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{'━'*30}\n"
            f"👨‍💻 {DEV_TAG}",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

async def on_shutdown(app):
    engine.stop_all()
    await chk.close()
    await db.close()
    logger.info("Bot stopped.")

# ══════════════════════════════════════════════════════════════════════
#  🏁 MAIN
# ══════════════════════════════════════════════════════════════════════

def main():
    # Start Flask keep-alive
    keep_alive()

    # Build application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(on_start)
        .post_shutdown(on_shutdown)
        .concurrent_updates(True)
        .build()
    )

    # ─── User handlers ─────────────────────────────────────
    application.add_handler(CommandHandler("start",   cmd_start))
    application.add_handler(CommandHandler("help",    cmd_help))
    application.add_handler(CommandHandler("buy",     cmd_buy))
    application.add_handler(CommandHandler("hunt",    cmd_hunt))
    application.add_handler(CommandHandler("check",   cmd_check))
    application.add_handler(CommandHandler("stop",    cmd_stop))
    application.add_handler(CommandHandler("stats",   cmd_stats))
    application.add_handler(CommandHandler("found",   cmd_found))
    application.add_handler(CommandHandler("sub",     cmd_sub))
    application.add_handler(CommandHandler("custom",  cmd_custom))
    application.add_handler(CommandHandler("prefix",  cmd_prefix))
    application.add_handler(CommandHandler("suffix",  cmd_suffix))

    # ─── Admin handlers ─────────────────────────────────────
    application.add_handler(CommandHandler("admin",            cmd_admin))
    application.add_handler(CommandHandler("activate",         cmd_activate))
    application.add_handler(CommandHandler("deactivate",       cmd_deactivate))
    application.add_handler(CommandHandler("ban",              cmd_ban))
    application.add_handler(CommandHandler("unban",            cmd_unban))
    application.add_handler(CommandHandler("extend",           cmd_extend))
    application.add_handler(CommandHandler("vip",              cmd_vip))
    application.add_handler(CommandHandler("broadcast",        cmd_broadcast))
    application.add_handler(CommandHandler("broadcast_active", cmd_broadcast_active))
    application.add_handler(CommandHandler("userinfo",         cmd_userinfo))
    application.add_handler(CommandHandler("allstats",         cmd_allstats))
    application.add_handler(CommandHandler("users",            cmd_users))
    application.add_handler(CommandHandler("stopall",          cmd_stopall))
    application.add_handler(CommandHandler("foundall",         cmd_foundall))
    application.add_handler(CommandHandler("logs",             cmd_logs))
    application.add_handler(CommandHandler("backup",           cmd_backup))
    application.add_handler(CommandHandler("payments",         cmd_payments))
    application.add_handler(CommandHandler("clearcache",       cmd_clearcache))
    application.add_handler(CommandHandler("addstars",         cmd_addstars))

    # ─── Payment handlers ───────────────────────────────────
    application.add_handler(PreCheckoutQueryHandler(pre_checkout))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    # ─── Callback handler ────────────────────────────────────
    application.add_handler(CallbackQueryHandler(handle_cb))

    # ─── Error handler ───────────────────────────────────────
    application.add_error_handler(error_handler)

    # ─── Run ──────────────────────────────────────────────────
    logger.info("🚀 بدء تشغيل البوت...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        close_loop=False
    )

if __name__ == "__main__":
    main()
