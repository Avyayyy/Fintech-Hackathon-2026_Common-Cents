"""
Pinnacle — Flask Backend
Handles:
  POST /api/wellness   — calculates wellness scores from portfolio data
  POST /api/scenario   — runs stress-test scenario math
  GET  /api/health     — simple liveness check
"""

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)   # allow the HTML file (file:// or any origin) to call these endpoints


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def calc_alloc_pct(assets: list) -> dict:
    """Return allocation percentages by asset type."""
    by_type: dict = {}
    total = sum(a["value"] for a in assets)
    if total == 0:
        return {}
    for a in assets:
        by_type[a["type"]] = by_type.get(a["type"], 0) + a["value"]
    return {k: round((v / total) * 100, 1) for k, v in by_type.items()}


def calc_liquid_cash(assets: list) -> float:
    return sum(a["value"] for a in assets if a["type"] == "cash")


# ─────────────────────────────────────────────────────────────────
# SCENARIO DEFINITIONS  (single source of truth — matches frontend)
# ─────────────────────────────────────────────────────────────────

SCENARIOS = {
    "crypto": {
        "desc": (
            "A significant correction in crypto markets driven by regulatory action or "
            "macro deleveraging. Bitcoin and other digital assets sell off sharply. "
            "Equities dip on risk-off sentiment."
        ),
        "worst_type": "crypto",
        "cash_impact": "Unaffected",
        "bull": False,
    },
    "rate": {
        "desc": (
            "The central bank raises rates by 1%, compressing bond valuations and "
            "impacting growth equities. Fixed income prices fall; cash and "
            "short-term deposits benefit slightly."
        ),
        "worst_type": "fixed",
        "cash_impact": "Slight drag (−0.3%)",
        "bull": False,
    },
    "recession": {
        "desc": (
            "A broad market sell-off driven by recession fears. Equities and real "
            "estate most exposed. Fixed income and cash act as safe havens."
        ),
        "worst_type": "equities",
        "cash_impact": "Unaffected",
        "bull": False,
    },
    "bull": {
        "desc": (
            "A strong risk-on environment driven by positive macro data and earnings "
            "beats. Equities and crypto surge; fixed income sees modest outflows."
        ),
        "worst_type": "equities",
        "cash_impact": "Unaffected",
        "bull": True,
    },
}


# ─────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "pinnacle-backend"})


@app.route("/api/wellness", methods=["POST"])
def wellness():
    """
    Request body:
    {
      "assets":           [ { "id", "name", "type", "value", ... } ],
      "targetAllocations": { "equities": 35, "realestate": 20, ... },
      "monthlyExpenses":  12000
    }

    Response:
    {
      "diversification": 78,
      "liquidity":       61,
      "volatility":      63,
      "behavioural":     68,
      "overall":         68,
      "monthsCovered":   23.5
    }
    """
    body = request.get_json(force=True)
    assets           = body.get("assets", [])
    targets          = body.get("targetAllocations", {})
    monthly_expenses = float(body.get("monthlyExpenses", 12000))

    alloc  = calc_alloc_pct(assets)
    total  = sum(a["value"] for a in assets)
    liquid = calc_liquid_cash(assets)
    months_covered = round(liquid / monthly_expenses, 1) if monthly_expenses > 0 else 0

    # ── Diversification ──────────────────────────────────────────
    div_score = 82
    for asset_type, target_pct in targets.items():
        diff = abs(alloc.get(asset_type, 0) - target_pct)
        if diff > 5:
            div_score -= 4
        if diff > 10:
            div_score -= 4
    div_score = max(20, min(100, div_score))

    # ── Liquidity ─────────────────────────────────────────────────
    liq_score = round(min(100, (months_covered / 3) * 75))

    # ── Volatility ────────────────────────────────────────────────
    crypto_pct = alloc.get("crypto", 0)
    eq_pct     = alloc.get("equities", 0)
    vol_score  = 70
    if crypto_pct > 10:
        vol_score -= 15
    elif crypto_pct > 5:
        vol_score -= 7
    if eq_pct > 50:
        vol_score -= 10
    elif eq_pct > 40:
        vol_score -= 5
    vol_score = max(20, min(100, vol_score))

    # ── Behavioural (history-based, static for now) ───────────────
    beh_score = 68

    overall = round((div_score + liq_score + vol_score + beh_score) / 4)

    return jsonify({
        "diversification": div_score,
        "liquidity":       liq_score,
        "volatility":      vol_score,
        "behavioural":     beh_score,
        "overall":         overall,
        "monthsCovered":   months_covered,
    })


@app.route("/api/scenario", methods=["POST"])
def scenario():
    """
    Request body:
    {
      "scenario":  "crypto" | "rate" | "recession" | "bull",
      "severity":  30,           // 5–60 (percentage)
      "assets":    [ ... ],
      "wellnessScore": 68
    }

    Response:
    {
      "scenarioKey":    "crypto",
      "description":    "...",
      "bull":           false,
      "sign":           "−",
      "total":          1177600,
      "newNetWorth":    1140872,
      "delta":          -36728,
      "changePct":      "-3.1",
      "currentWellness": 68,
      "newWellness":     61,
      "worstAssetName": "Bitcoin",
      "cashImpact":     "Unaffected",
      "exposurePct":    5.2
    }
    """
    body         = request.get_json(force=True)
    scen_key     = body.get("scenario", "crypto")
    severity     = int(body.get("severity", 30))
    assets       = body.get("assets", [])
    wellness_score = int(body.get("wellnessScore", 68))

    s = SCENARIOS.get(scen_key, SCENARIOS["crypto"])
    alloc = calc_alloc_pct(assets)
    total = sum(a["value"] for a in assets)

    exposure_pct  = alloc.get(s["worst_type"], 0) / 100
    direction     = 1 if s["bull"] else -1
    delta         = direction * (severity / 100) * exposure_pct * total
    new_nw        = round(total + delta)
    change_pct    = round((delta / total) * 100, 1) if total else 0

    w_delta   = round(severity * 0.08) if s["bull"] else -round(severity * 0.12)
    new_wellness = max(0, min(100, wellness_score + w_delta))

    # Worst-hit asset (largest value in the affected type)
    affected = [a for a in assets if a["type"] == s["worst_type"]]
    worst_asset = max(affected, key=lambda a: a["value"]) if affected else None

    return jsonify({
        "scenarioKey":     scen_key,
        "description":     s["desc"],
        "bull":            s["bull"],
        "sign":            "+" if s["bull"] else "−",
        "total":           total,
        "newNetWorth":     new_nw,
        "delta":           round(delta),
        "changePct":       str(change_pct),
        "currentWellness": wellness_score,
        "newWellness":     new_wellness,
        "worstAssetName":  worst_asset["name"] if worst_asset else None,
        "cashImpact":      s["cash_impact"],
        "exposurePct":     round(alloc.get(s["worst_type"], 0), 1),
    })


# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
