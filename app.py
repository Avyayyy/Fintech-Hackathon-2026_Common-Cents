"""
Pinnacle — Flask Backend
Auth:
  POST /api/auth/register  — create account
  POST /api/auth/login     — returns JWT token
  GET  /api/auth/me        — get profile (requires token)
  POST /api/auth/save      — save portfolio data (requires token)

Calculations:
  POST /api/wellness       — wellness score calculation
  POST /api/scenario       — stress test simulation
  GET  /api/health         — liveness check
"""

import os
import json
import sqlite3
import hashlib
import hmac
import base64
import time
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

SECRET_KEY = os.environ.get("SECRET_KEY", "pinnacle-dev-secret-change-in-prod")
DB_PATH    = os.environ.get("DB_PATH", "pinnacle.db")

DEFAULT_ASSETS = [
    {"id":"ocbc","name":"OCBC Savings","type":"cash","value":142000,"change":0.4,"icon":"🏦","bg":"#EEF2FF"},
    {"id":"spx","name":"S&P 500 ETF","type":"equities","value":310000,"change":3.8,"icon":"📊","bg":"#E8F0FB"},
    {"id":"mlt","name":"Mapletree REIT","type":"realestate","value":200000,"change":0.1,"icon":"🏠","bg":"#F0FDF4"},
    {"id":"btc","name":"Bitcoin","type":"crypto","value":61400,"change":-2.1,"icon":"₿","bg":"#FFF7ED"},
    {"id":"sgb","name":"SG Govt Bond 2031","type":"fixed","value":120000,"change":0.2,"icon":"💎","bg":"#F5F0FF"},
    {"id":"sti","name":"STI ETF","type":"equities","value":98000,"change":1.2,"icon":"🇸🇬","bg":"#EEF2FF"},
    {"id":"eem","name":"MSCI EM ETF","type":"equities","value":54000,"change":-0.9,"icon":"🌍","bg":"#EEF2FF"},
    {"id":"uob","name":"UOB Fixed Deposit","type":"fixed","value":50000,"change":0.0,"icon":"🏢","bg":"#FEF3E2","maturesDays":14},
    {"id":"dbs","name":"DBS Savings","type":"cash","value":142200,"change":0.0,"icon":"🏦","bg":"#E8F4FD"},
]
DEFAULT_TARGETS  = {"equities":35,"realestate":20,"fixed":15,"cash":20,"crypto":5,"private":5}
DEFAULT_EXPENSES = 12000

SCENARIOS = {
    "crypto":    {"desc":"A significant correction in crypto markets driven by regulatory action or macro deleveraging. Bitcoin and other digital assets sell off sharply. Equities dip on risk-off sentiment.","worst_type":"crypto","cash_impact":"Unaffected","bull":False},
    "rate":      {"desc":"The central bank raises rates by 1%, compressing bond valuations and impacting growth equities. Fixed income prices fall; cash and short-term deposits benefit slightly.","worst_type":"fixed","cash_impact":"Slight drag (−0.3%)","bull":False},
    "recession": {"desc":"A broad market sell-off driven by recession fears. Equities and real estate most exposed. Fixed income and cash act as safe havens.","worst_type":"equities","cash_impact":"Unaffected","bull":False},
    "bull":      {"desc":"A strong risk-on environment driven by positive macro data and earnings beats. Equities and crypto surge; fixed income sees modest outflows.","worst_type":"equities","cash_impact":"Unaffected","bull":True},
}

# ── DB ────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
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
    """)
    conn.commit()
    conn.close()

init_db()

# ── TOKEN HELPERS ─────────────────────────────────────────────────
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
        if time.time() - int(ts) > 7 * 24 * 3600:
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

# ── CALC HELPERS ──────────────────────────────────────────────────
def calc_alloc_pct(assets):
    by_type = {}
    total = sum(a["value"] for a in assets)
    if total == 0:
        return {}
    for a in assets:
        by_type[a["type"]] = by_type.get(a["type"], 0) + a["value"]
    return {k: round((v / total) * 100, 1) for k, v in by_type.items()}

def calc_liquid_cash(assets):
    return sum(a["value"] for a in assets if a["type"] == "cash")

# ── AUTH ROUTES ───────────────────────────────────────────────────
@app.route("/api/auth/register", methods=["POST"])
def register():
    body  = request.get_json(force=True)
    name  = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    pw    = body.get("password") or ""

    if not name:           return jsonify({"error": "Name is required"}), 400
    if "@" not in email:   return jsonify({"error": "Valid email required"}), 400
    if len(pw) < 8:        return jsonify({"error": "Password must be at least 8 characters"}), 400

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (name,email,password_hash,assets,targets,monthly_expenses,created_at) VALUES (?,?,?,?,?,?,?)",
            (name, email, hash_password(pw), json.dumps(DEFAULT_ASSETS), json.dumps(DEFAULT_TARGETS), DEFAULT_EXPENSES, int(time.time()))
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "An account with this email already exists"}), 409
    finally:
        conn.close()

    return jsonify({"token": make_token(email), "name": name, "email": email,
                    "assets": DEFAULT_ASSETS, "targets": DEFAULT_TARGETS,
                    "monthlyExpenses": DEFAULT_EXPENSES}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    body  = request.get_json(force=True)
    email = (body.get("email") or "").strip().lower()
    pw    = body.get("password") or ""

    conn = get_db()
    row  = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()

    if not row or row["password_hash"] != hash_password(pw):
        return jsonify({"error": "Incorrect email or password"}), 401

    return jsonify({
        "token":           make_token(email),
        "name":            row["name"],
        "email":           row["email"],
        "assets":          json.loads(row["assets"]),
        "targets":         json.loads(row["targets"]),
        "monthlyExpenses": row["monthly_expenses"],
    })


@app.route("/api/auth/me", methods=["GET"])
def me():
    email, err = require_auth()
    if err: return err
    conn = get_db()
    row  = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    if not row: return jsonify({"error": "User not found"}), 404
    return jsonify({
        "name": row["name"], "email": row["email"],
        "assets": json.loads(row["assets"]),
        "targets": json.loads(row["targets"]),
        "monthlyExpenses": row["monthly_expenses"],
    })


@app.route("/api/auth/save", methods=["POST"])
def save_portfolio():
    email, err = require_auth()
    if err: return err
    body = request.get_json(force=True)
    conn = get_db()
    if body.get("assets")          is not None: conn.execute("UPDATE users SET assets=? WHERE email=?",           (json.dumps(body["assets"]), email))
    if body.get("targets")         is not None: conn.execute("UPDATE users SET targets=? WHERE email=?",          (json.dumps(body["targets"]), email))
    if body.get("monthlyExpenses") is not None: conn.execute("UPDATE users SET monthly_expenses=? WHERE email=?", (float(body["monthlyExpenses"]), email))
    conn.commit()
    conn.close()
    return jsonify({"status": "saved"})


# ── CALC ROUTES ───────────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "pinnacle-backend"})


@app.route("/api/wellness", methods=["POST"])
def wellness():
    body             = request.get_json(force=True)
    assets           = body.get("assets", [])
    targets          = body.get("targetAllocations", {})
    monthly_expenses = float(body.get("monthlyExpenses", 12000))

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
