"""
Pinnacle — Flask Backend
Supports SQLite (local) and PostgreSQL (Render) via DATABASE_URL env var.
"""

import os, json, hashlib, hmac, base64, time
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

SECRET_KEY = os.environ.get("SECRET_KEY", "pinnacle-dev-secret-change-in-prod")
DATABASE_URL = os.environ.get("DATABASE_URL")  # Set on Render for PostgreSQL

# ── DB abstraction (SQLite locally, PostgreSQL on Render) ─────────
USE_PG = bool(DATABASE_URL)

if USE_PG:
    import psycopg2
    import psycopg2.extras
    # Render gives postgres:// but psycopg2 needs postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    def get_db():
        conn = psycopg2.connect(DATABASE_URL)
        return conn

    def db_exec(sql, params=(), fetchone=False, fetchall=False, commit=False):
        # Convert SQLite ? placeholders to PostgreSQL %s
        sql = sql.replace("?", "%s")
        conn = get_db()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql, params)
            if commit:
                conn.commit()
            if fetchone:
                return cur.fetchone()
            if fetchall:
                return cur.fetchall()
        finally:
            conn.close()
        return None
else:
    import sqlite3
    DB_PATH = os.environ.get("DB_PATH", "pinnacle.db")

    def get_db():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def db_exec(sql, params=(), fetchone=False, fetchall=False, commit=False):
        conn = get_db()
        try:
            cur = conn.execute(sql, params)
            if commit:
                conn.commit()
            if fetchone:
                return cur.fetchone()
            if fetchall:
                return cur.fetchall()
        finally:
            conn.close()
        return None

# ── Init DB ───────────────────────────────────────────────────────
def init_db():
    if USE_PG:
        db_exec("""
            CREATE TABLE IF NOT EXISTS users (
                id               SERIAL PRIMARY KEY,
                name             TEXT    NOT NULL,
                email            TEXT    NOT NULL UNIQUE,
                password_hash    TEXT    NOT NULL,
                assets           TEXT    NOT NULL DEFAULT '[]',
                targets          TEXT    NOT NULL DEFAULT '{}',
                monthly_expenses REAL    NOT NULL DEFAULT 12000,
                created_at       BIGINT  NOT NULL
            )
        """, commit=True)
    else:
        db_exec("""
            CREATE TABLE IF NOT EXISTS users (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                name             TEXT    NOT NULL,
                email            TEXT    NOT NULL UNIQUE,
                password_hash    TEXT    NOT NULL,
                assets           TEXT    NOT NULL DEFAULT '[]',
                targets          TEXT    NOT NULL DEFAULT '{}',
                monthly_expenses REAL    NOT NULL DEFAULT 12000,
                created_at       INTEGER NOT NULL
            )
        """, commit=True)

init_db()

DEFAULT_ASSETS  = []
DEFAULT_TARGETS = {"equities":35,"realestate":20,"fixed":15,"cash":20,"crypto":5,"private":5}
DEFAULT_EXPENSES = 12000

SCENARIOS = {
    "crypto":    {"desc":"A significant correction in crypto markets driven by regulatory action or macro deleveraging. Bitcoin and other digital assets sell off sharply.","worst_type":"crypto","cash_impact":"Unaffected","bull":False},
    "rate":      {"desc":"The central bank raises rates by 1%, compressing bond valuations and impacting growth equities. Fixed income prices fall.","worst_type":"fixed","cash_impact":"Slight drag (−0.3%)","bull":False},
    "recession": {"desc":"A broad market sell-off driven by recession fears. Equities and real estate most exposed. Fixed income and cash act as safe havens.","worst_type":"equities","cash_impact":"Unaffected","bull":False},
    "bull":      {"desc":"A strong risk-on environment driven by positive macro data and earnings beats. Equities and crypto surge.","worst_type":"equities","cash_impact":"Unaffected","bull":True},
}

# ── Auth helpers ──────────────────────────────────────────────────
def hash_password(password):
    return hmac.new(SECRET_KEY.encode(), password.encode(), hashlib.sha256).hexdigest()

def make_token(email):
    payload = f"{email}|{int(time.time())}"
    payload_b64 = base64.b64encode(payload.encode()).decode()
    sig = hmac.new(SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"

def verify_token(token):
    try:
        payload_b64, sig = token.rsplit(".", 1)
        expected = hmac.new(SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = base64.b64decode(payload_b64.encode()).decode()
        email, ts = payload.rsplit("|", 1)
        if time.time() - int(ts) > 30 * 24 * 3600:  # 30 days
            return None
        return email
    except Exception:
        return None

def require_auth():
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else None
    if not token:
        return None, (jsonify({"error": "Missing token"}), 401)
    email = verify_token(token)
    if not email:
        return None, (jsonify({"error": "Invalid or expired token — please log in again"}), 401)
    return email, None

# ── Calc helpers ──────────────────────────────────────────────────
def calc_alloc_pct(assets):
    by_type = {}
    total = sum(a["value"] for a in assets)
    if total == 0: return {}
    for a in assets:
        by_type[a["type"]] = by_type.get(a["type"], 0) + a["value"]
    return {k: round((v / total) * 100, 1) for k, v in by_type.items()}

def calc_liquid_cash(assets):
    return sum(a["value"] for a in assets if a["type"] == "cash")

def row_to_dict(row):
    """Convert sqlite3.Row or psycopg2 RealDictRow to plain dict."""
    if row is None: return None
    return dict(row)

# ── Auth routes ───────────────────────────────────────────────────
@app.route("/api/auth/register", methods=["POST"])
def register():
    body  = request.get_json(force=True)
    name  = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    pw    = body.get("password") or ""

    if not name:         return jsonify({"error": "Name is required"}), 400
    if "@" not in email: return jsonify({"error": "Valid email required"}), 400
    if len(pw) < 8:      return jsonify({"error": "Password must be at least 8 characters"}), 400

    try:
        db_exec(
            "INSERT INTO users (name,email,password_hash,assets,targets,monthly_expenses,created_at) VALUES (?,?,?,?,?,?,?)",
            (name, email, hash_password(pw), json.dumps(DEFAULT_ASSETS), json.dumps(DEFAULT_TARGETS), DEFAULT_EXPENSES, int(time.time())),
            commit=True
        )
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return jsonify({"error": "An account with this email already exists"}), 409
        return jsonify({"error": "Registration failed — please try again"}), 500

    return jsonify({
        "token": make_token(email), "name": name, "email": email,
        "assets": DEFAULT_ASSETS, "targets": DEFAULT_TARGETS,
        "monthlyExpenses": DEFAULT_EXPENSES, "createdAt": int(time.time())
    }), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    body  = request.get_json(force=True)
    email = (body.get("email") or "").strip().lower()
    pw    = body.get("password") or ""

    row = row_to_dict(db_exec("SELECT * FROM users WHERE email=?", (email,), fetchone=True))
    if not row or row["password_hash"] != hash_password(pw):
        return jsonify({"error": "Incorrect email or password"}), 401

    return jsonify({
        "token":           make_token(email),
        "name":            row["name"],
        "email":           row["email"],
        "assets":          json.loads(row["assets"]),
        "targets":         json.loads(row["targets"]),
        "monthlyExpenses": row["monthly_expenses"],
        "createdAt":       row["created_at"],
    })


@app.route("/api/auth/me", methods=["GET"])
def me():
    email, err = require_auth()
    if err: return err
    row = row_to_dict(db_exec("SELECT * FROM users WHERE email=?", (email,), fetchone=True))
    if not row: return jsonify({"error": "User not found"}), 404
    return jsonify({
        "name": row["name"], "email": row["email"],
        "assets": json.loads(row["assets"]),
        "targets": json.loads(row["targets"]),
        "monthlyExpenses": row["monthly_expenses"],
        "createdAt": row["created_at"],
    })


@app.route("/api/auth/save", methods=["POST"])
def save_portfolio():
    email, err = require_auth()
    if err: return err
    body = request.get_json(force=True)
    if body.get("assets")          is not None:
        db_exec("UPDATE users SET assets=? WHERE email=?",           (json.dumps(body["assets"]), email), commit=True)
    if body.get("targets")         is not None:
        db_exec("UPDATE users SET targets=? WHERE email=?",          (json.dumps(body["targets"]), email), commit=True)
    if body.get("monthlyExpenses") is not None:
        db_exec("UPDATE users SET monthly_expenses=? WHERE email=?", (float(body["monthlyExpenses"]), email), commit=True)
    return jsonify({"status": "saved"})


# ── Calc routes ───────────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "pinnacle-backend", "db": "postgres" if USE_PG else "sqlite"})


@app.route("/api/wellness", methods=["POST"])
def wellness():
    body             = request.get_json(force=True)
    assets           = body.get("assets", [])
    targets          = body.get("targetAllocations", {})
    monthly_expenses = float(body.get("monthlyExpenses", 12000))

    if not assets:
        return jsonify({"diversification":0,"liquidity":0,"volatility":0,"behavioural":0,"overall":0,"monthsCovered":0})

    alloc  = calc_alloc_pct(assets)
    liquid = calc_liquid_cash(assets)
    months_covered = round(liquid / monthly_expenses, 1) if monthly_expenses > 0 else 0

    div_score = 82
    for t, tp in targets.items():
        diff = abs(alloc.get(t, 0) - tp)
        if diff > 5:  div_score -= 4
        if diff > 10: div_score -= 4
    div_score = max(20, min(100, div_score))

    liq_score  = round(min(100, (months_covered / 3) * 75))
    crypto_pct = alloc.get("crypto", 0)
    eq_pct     = alloc.get("equities", 0)
    vol_score  = 70
    if crypto_pct > 10:  vol_score -= 15
    elif crypto_pct > 5: vol_score -= 7
    if eq_pct > 50:      vol_score -= 10
    elif eq_pct > 40:    vol_score -= 5
    vol_score = max(20, min(100, vol_score))

    beh_score = 68
    overall   = round((div_score + liq_score + vol_score + beh_score) / 4)
    return jsonify({"diversification": div_score, "liquidity": liq_score,
                    "volatility": vol_score, "behavioural": beh_score,
                    "overall": overall, "monthsCovered": months_covered})


@app.route("/api/scenario", methods=["POST"])
def scenario():
    body           = request.get_json(force=True)
    scen_key       = body.get("scenario", "crypto")
    severity       = int(body.get("severity", 30))
    assets         = body.get("assets", [])
    wellness_score = int(body.get("wellnessScore", 68))

    s     = SCENARIOS.get(scen_key, SCENARIOS["crypto"])
    alloc = calc_alloc_pct(assets)
    total = sum(a["value"] for a in assets)

    exposure_pct = alloc.get(s["worst_type"], 0) / 100
    direction    = 1 if s["bull"] else -1
    delta        = direction * (severity / 100) * exposure_pct * total
    new_nw       = round(total + delta)
    change_pct   = round((delta / total) * 100, 1) if total else 0
    w_delta      = round(severity * 0.08) if s["bull"] else -round(severity * 0.12)
    new_wellness = max(0, min(100, wellness_score + w_delta))

    affected    = [a for a in assets if a["type"] == s["worst_type"]]
    worst_asset = max(affected, key=lambda a: a["value"]) if affected else None

    return jsonify({
        "scenarioKey": scen_key, "description": s["desc"], "bull": s["bull"],
        "sign": "+" if s["bull"] else "−",
        "total": total, "newNetWorth": new_nw,
        "delta": round(delta), "changePct": str(change_pct),
        "currentWellness": wellness_score, "newWellness": new_wellness,
        "worstAssetName": worst_asset["name"] if worst_asset else None,
        "cashImpact": s["cash_impact"],
        "exposurePct": round(alloc.get(s["worst_type"], 0), 1),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
