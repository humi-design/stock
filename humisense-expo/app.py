"""HUMISENSE AI Operations Workforce — Money Expo 2026 demo build.

A Flask application demonstrating AI-powered reconciliation and exception
resolution. Demo-first: works fully offline with deterministic synthetic
data and a Mock AI provider. No AI API is required.
"""
import json
import os
import time
from datetime import datetime

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

from config import config
from db import db
import demo_data
import reconciliation
from ai_gateway import current_provider_label, get_provider, investigate_case
from roi import calculate, hero_estimate

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

NOT_FOUND = "NOT_IN_DB"


# --------------------------------------------------------------------- #
# Jinja helpers
# --------------------------------------------------------------------- #
def fmt_inr(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "₹0"
    s = f"{v:,.0f}"
    return f"₹{s}"


def fmt_amount(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "₹0"
    if v == int(v):
        return f"₹{int(v):,}"
    return f"₹{v:,.2f}"


def compact_inr(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "₹0"
    if v >= 10000000:
        return f"₹{v/10000000:.1f} Cr"
    if v >= 100000:
        return f"₹{v/100000:.1f} L"
    if v >= 1000:
        return f"₹{v/1000:.0f} K"
    return f"₹{v:,.0f}"


def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds")


def severity_badge_cls(sev):
    return {
        "CRITICAL": "badge-critical",
        "HIGH": "badge-high",
        "MEDIUM": "badge-medium",
        "LOW": "badge-low",
    }.get((sev or "").upper(), "badge-low")


def status_cls(status):
    return {
        "Resolved": "badge-success",
        "AI Recommended": "badge-info",
        "Investigated": "badge-info",
        "Awaiting Review": "badge-warn",
        "Awaiting Approval": "badge-warn",
        "Pending Approval": "badge-warn",
        "Rejected": "badge-danger",
        "Escalated": "badge-danger",
        "New": "badge-neutral",
    }.get(status, "badge-neutral")


app.jinja_env.filters["inr"] = fmt_inr
app.jinja_env.filters["money"] = fmt_amount
app.jinja_env.filters["compact_inr"] = compact_inr
app.jinja_env.globals["severity_badge_cls"] = severity_badge_cls
app.jinja_env.globals["status_cls"] = status_cls
app.jinja_env.globals["current_provider_label"] = current_provider_label
app.jinja_env.globals["reconciliation_label"] = (
    lambda t: reconciliation.CASE_TYPES.get(t, t))


# --------------------------------------------------------------------- #
# Demo state helpers
# --------------------------------------------------------------------- #
def get_recon_summary():
    row = db.query_one("SELECT value FROM settings WHERE key='recon_summary'")
    if not row:
        return None
    try:
        return json.loads(row["value"])
    except Exception:
        return None


def set_recon_summary(summary):
    value = json.dumps(summary)
    if db.engine == "mysql":
        db.execute(
            "INSERT INTO settings (`key`, value) VALUES (%s,%s) "
            "ON DUPLICATE KEY UPDATE value=%s", ("recon_summary", value, value))
    else:
        db.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=?", ("recon_summary", value, value))


def clear_recon_summary():
    db.execute("DELETE FROM settings WHERE key='recon_summary'")


def _case_exists(case_ref):
    row = db.query_one("SELECT id FROM cases WHERE case_ref=%s"
                       if db.engine == "mysql" else
                       "SELECT id FROM cases WHERE case_ref=?",
                       (case_ref,))
    return row is not None


def save_case(exc):
    """Persist an exception as a Case (generic Case Engine model)."""
    if _case_exists(exc["case_ref"]):
        return False
    _insert_case(exc)
    # Seed the opening audit event for every new case.
    add_event(exc["case_ref"], "exception",
              "Exception detected during reconciliation.")
    return True


def _insert_case(exc):
    evidence = json.dumps({"bank": exc.get("bank"), "broker": exc.get("broker"),
                           "settlement": exc.get("settlement")})
    # Seed the deterministic demo-AI confidence so the queue reads well
    # before an investigation is run.
    from ai_gateway import _mock_confidence
    confidence = exc.get("confidence") or _mock_confidence(exc["case_type"])
    if db.engine == "mysql":
        db.execute(
            "INSERT INTO cases (case_ref, case_type, reference, amount, currency, "
            "severity, status, root_cause, recommendation, confidence, evidence, "
            "created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (exc["case_ref"], exc["case_type"], exc["reference"], exc["amount"],
             exc["currency"], exc["severity"], "AI Recommended", None, None,
             confidence, evidence, now_iso()))
    else:
        db.execute(
            "INSERT INTO cases (case_ref, case_type, reference, amount, currency, "
            "severity, status, root_cause, recommendation, confidence, evidence, "
            "created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (exc["case_ref"], exc["case_type"], exc["reference"], exc["amount"],
             exc["currency"], exc["severity"], "AI Recommended", None, None,
             confidence, evidence, now_iso()))


def get_case(case_ref):
    row = db.query_one("SELECT * FROM cases WHERE case_ref=%s"
                       if db.engine == "mysql" else
                       "SELECT * FROM cases WHERE case_ref=?", (case_ref,))
    if not row:
        return None
    case = db.row_to_dict(row)
    case["evidence"] = _load_evidence(case.get("evidence"))
    return case


def _load_evidence(raw):
    if not raw:
        return {"bank": None, "broker": None, "settlement": None}
    try:
        return json.loads(raw)
    except Exception:
        return {"bank": None, "broker": None, "settlement": None}


def add_event(case_ref, event_type, detail=""):
    case = get_case(case_ref)
    if not case:
        return
    if db.engine == "mysql":
        db.execute(
            "INSERT INTO case_events (case_id, event_type, detail, created_at) "
            "VALUES (%s,%s,%s,%s)",
            (case["id"], event_type, detail, now_iso()))
    else:
        db.execute(
            "INSERT INTO case_events (case_id, event_type, detail, created_at) "
            "VALUES (?,?,?,?)",
            (case["id"], event_type, detail, now_iso()))


def _rationale_for_case(case):
    ctype = case.get("case_type", "")
    if ctype == "SETTLEMENT_MISMATCH":
        return ("3 related records found · 2 systems confirm settlement · "
                "1 system shows pending ledger entry · No conflicting transaction detected")
    if ctype == "DUPLICATE_TRANSACTION":
        return ("An identical transaction profile found in the bank stream · "
                "No conflicting transaction detected")
    if ctype == "MISSING_TRANSACTION":
        return ("Transaction present in bank stream with no downstream records · "
                "No conflicting transaction detected")
    if ctype == "AMOUNT_MISMATCH":
        return ("Amounts differ between bank and broker records · "
                "No conflicting transaction detected")
    if ctype == "DATE_MISMATCH":
        return ("Value dates differ beyond configured tolerance · "
                "No conflicting transaction detected")
    if ctype == "ACCOUNT_MISMATCH":
        return ("Account references differ between systems · "
                "No conflicting transaction detected")
    if ctype == "STATUS_MISMATCH":
        return ("Status values differ between systems · "
                "No conflicting transaction detected")
    return "Related records compared across systems · No conflicting transaction detected"


def get_events(case_ref):
    case = get_case(case_ref)
    if not case:
        return []
    rows = db.query("SELECT * FROM case_events WHERE case_id=%s ORDER BY id"
                    if db.engine == "mysql" else
                    "SELECT * FROM case_events WHERE case_id=? ORDER BY id",
                    (case["id"],))
    return [db.row_to_dict(r) for r in rows]


def update_case(case_ref, **fields):
    sets = ", ".join(f"{k}=%s" if db.engine == "mysql" else f"{k}=?" for k in fields)
    params = list(fields.values())
    params.append(case_ref)
    db.execute(f"UPDATE cases SET {sets} WHERE case_ref=%s"
               if db.engine == "mysql" else
               f"UPDATE cases SET {sets} WHERE case_ref=?", params)


def list_cases(filters=None):
    filters = filters or {}
    sql = "SELECT * FROM cases WHERE 1=1"
    params = []
    severity = filters.get("severity")
    if severity and severity != "all":
        if severity == "critical":
            sql += " AND severity=%s AND amount >= 100000" if db.engine == "mysql" \
                else " AND severity=? AND amount >= 100000"
            params += ["HIGH"]
        elif severity == "resolved":
            sql += " AND status=%s" if db.engine == "mysql" else " AND status=?"
            params += ["Resolved"]
        else:
            sql += " AND severity=%s" if db.engine == "mysql" else " AND severity=?"
            params.append(severity.upper())
    sql += " ORDER BY CASE WHEN reference='TXN-82931' THEN 0 ELSE 1 END, reference DESC"
    rows = db.query(sql, params)
    cases = [db.row_to_dict(r) for r in rows]
    for c in cases:
        c["evidence"] = _load_evidence(c.get("evidence"))
    return cases


def run_reconciliation(bank_file=None, broker_file=None, settlement_file=None):
    """Run the deterministic reconciliation engine and persist cases."""
    if bank_file and broker_file and settlement_file:
        result = reconciliation.run_file_reconciliation(bank_file, broker_file, settlement_file)
    else:
        bank, broker, settlement = reconciliation.load_demo_files()
        result = reconciliation.reconcile(bank, broker, settlement)

    # Persist all exceptions as cases.
    case_count = 0
    for exc in result.exceptions:
        exc["status"] = "New"
        before = None
        save_case(exc)
        case_count += 1

    summary = result.summary()
    summary["case_count"] = case_count
    if case_count:
        summary["hero_case_ref"] = "CASE #82931"
    set_recon_summary(summary)
    return summary, result.exceptions


def reset_demo():
    db.execute("DELETE FROM case_events")
    db.execute("DELETE FROM cases")
    clear_recon_summary()


# --------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------- #
@app.route("/")
def index():
    summary = get_recon_summary()
    return render_template("index.html", summary=summary)


@app.route("/dashboard")
def dashboard():
    summary = get_recon_summary()
    return render_template("dashboard.html",
                           summary=summary,
                           estimate=hero_estimate())


@app.route("/reconcile", methods=["POST"])
def reconcile_route():
    files = {}
    for key in ("bank", "broker", "settlement"):
        f = request.files.get(key)
        if f and f.filename:
            files[key] = f
    try:
        if len(files) > 0 and len(files) < 3:
            return jsonify({"ok": False,
                            "error": "Provide all three files (bank, broker, settlement) to run reconciliation on uploaded data."}), 400
        kwargs = {}
        if len(files) == 3:
            import tempfile
            tmp = {}
            for k, f in files.items():
                suffix = os.path.splitext(f.filename)[1] or ".csv"
                path = os.path.join(tempfile.gettempdir(),
                                    f"humisense_{k}_{time.time()}{suffix}")
                f.save(path)
                tmp[k] = path
            kwargs = {"bank_file": tmp["bank"], "broker_file": tmp["broker"],
                      "settlement_file": tmp["settlement"]}
        summary, exceptions = run_reconciliation(**kwargs)
        return jsonify({"ok": True, "summary": summary,
                        "hero_case_ref": summary.get("hero_case_ref")})
    except Exception as exc:
        app.logger.exception("Reconciliation failed")
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/exceptions")
def exceptions():
    severity = request.args.get("severity", "all")
    cases = list_cases({"severity": severity})
    summary = get_recon_summary()
    return render_template("exceptions.html", cases=cases,
                           summary=summary, active_severity=severity)


@app.route("/cases/<case_ref>")
def case_detail(case_ref):
    case = get_case(case_ref)
    if not case:
        flash("Case not found. Run a reconciliation first.")
        return redirect(url_for("exceptions"))
    events = get_events(case_ref)
    case["case_type_label"] = reconciliation.CASE_TYPES.get(case["case_type"], case["case_type"])
    investigation = None
    if case.get("root_cause") and case.get("recommendation"):
        investigation = {
            "what_happened": case["root_cause"],
            "root_cause": case["root_cause"],
            "recommendation": case["recommendation"],
            "confidence": case.get("confidence") or 0,
            "rationale": _rationale_for_case(case),
            "provider": "demo",
            "fallback": False,
        }
    return render_template("case_detail.html", case=case, events=events,
                           investigation=investigation)


@app.route("/cases/<case_ref>/investigate", methods=["POST"])
def investigate_route(case_ref):
    case = get_case(case_ref)
    if not case:
        return jsonify({"ok": False, "error": "Case not found"}), 404
    result = investigate_case(case)
    update_case(case_ref,
                root_cause=result["root_cause"],
                recommendation=result["recommendation"],
                confidence=result["confidence"],
                status="Investigated")
    if result.get("fallback"):
        add_event(case_ref, "fallback",
                  "Live AI unavailable — switched to Demo AI.")
    add_event(case_ref, "investigation_started", "AI investigation started.")
    add_event(case_ref, "evidence_collected",
              "Related records retrieved from bank, settlement and broker systems.")
    add_event(case_ref, "recommendation_created",
              "Root cause identified and resolution recommendation prepared.")
    case = get_case(case_ref)
    result["ok"] = True
    result["case_ref"] = case_ref
    result["label"] = reconciliation.CASE_TYPES.get(case["case_type"], case["case_type"])
    result["provider"] = result.get("provider", "demo")
    return jsonify(result)


@app.route("/cases/<case_ref>/action", methods=["POST"])
def case_action(case_ref):
    action = request.json.get("action") if request.is_json else request.form.get("action")
    case = get_case(case_ref)
    if not case:
        return jsonify({"ok": False, "error": "Case not found"}), 404
    if action == "approve":
        update_case(case_ref, status="Resolved")
        add_event(case_ref, "approval",
                  "Approved by Demo Operations Manager.")
        add_event(case_ref, "execution",
                  "Resolution action executed.")
        add_event(case_ref, "verification", "Verification completed.")
        add_event(case_ref, "resolution", "Case resolved.")
        return jsonify({"ok": True, "status": "Resolved"})
    if action == "reject":
        update_case(case_ref, status="Rejected")
        add_event(case_ref, "reject", "Resolution rejected by human operator.")
        return jsonify({"ok": True, "status": "Rejected"})
    if action == "escalate":
        update_case(case_ref, status="Escalated")
        add_event(case_ref, "escalate", "Case escalated to senior operations.")
        return jsonify({"ok": True, "status": "Escalated"})
    return jsonify({"ok": False, "error": "Unknown action"}), 400


@app.route("/cases/<case_ref>/approved", methods=["POST"])
def case_approved(case_ref):
    """Human approved a high-risk resolution - records the approval step."""
    case = get_case(case_ref)
    if not case:
        return jsonify({"ok": False, "error": "Case not found"}), 404
    update_case(case_ref, status="Awaiting Approval")
    add_event(case_ref, "approval_requested",
              "Approval requested from Demo Operations Manager.")
    return jsonify({"ok": True, "status": "Awaiting Approval"})


@app.route("/reset", methods=["POST"])
def reset_route():
    reset_demo()
    return jsonify({"ok": True})


@app.route("/start-demo", methods=["POST"])
def start_demo():
    """One-click demo: load synthetic data, reconcile, open hero case."""
    reset_demo()
    summary, exceptions = run_reconciliation()
    return jsonify({"ok": True, "summary": summary,
                    "hero_case_ref": summary.get("hero_case_ref")})


@app.route("/roi")
def roi():
    summary = get_recon_summary()
    return render_template("roi.html", summary=summary)


@app.route("/roi/calculate", methods=["POST"])
def roi_calculate():
    data = request.get_json(force=True, silent=True) or request.form
    est = calculate(
        monthly_exceptions=data.get("monthly_exceptions", 30000),
        handling_minutes=data.get("handling_minutes", 15),
        hourly_cost=data.get("hourly_cost", 500),
        ai_rate=data.get("ai_rate", 70),
        review_minutes=data.get("review_minutes", 3),
    )
    return jsonify({"ok": True, "estimate": est})


@app.route("/lead", methods=["GET", "POST"])
def lead():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        company = request.form.get("company", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        role = request.form.get("role", "").strip()
        company_type = request.form.get("company_type", "").strip()
        process = request.form.get("process", "").strip()
        try:
            if db.engine == "mysql":
                db.execute(
                    "INSERT INTO leads (name, company, email, phone, role, "
                    "company_type, process, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (name, company, email, phone, role, company_type, process, now_iso()))
            else:
                db.execute(
                    "INSERT INTO leads (name, company, email, phone, role, "
                    "company_type, process, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (name, company, email, phone, role, company_type, process, now_iso()))
            flash("Thank you. A Humisense representative will contact you.")
            return redirect(url_for("lead_thanks"))
        except Exception as exc:
            app.logger.exception("Lead save failed")
            flash("Sorry, we could not save your details. Please try again.")
            return redirect(url_for("lead"))
    return render_template("lead.html", summary=get_recon_summary())


@app.route("/lead/thanks")
def lead_thanks():
    return render_template("lead_thanks.html", summary=get_recon_summary())


@app.route("/settings")
def settings_page():
    rows = db.query("SELECT * FROM settings")
    current = {r["key"]: r["value"] for r in rows}
    provider = current.get("ai_provider", config.AI_PROVIDER or "mock")
    base_url = current.get("ai_base_url", config.AI_BASE_URL)
    model = current.get("ai_model", config.AI_MODEL)
    api_key = current.get("ai_api_key", config.AI_API_KEY)
    mask = mask_key(api_key)
    return render_template("settings.html", provider=provider, base_url=base_url,
                           model=model, api_key=mask, demo_mode=config.DEMO_MODE)


@app.route("/settings/save", methods=["POST"])
def settings_save():
    provider = request.form.get("ai_provider", "mock").strip().lower()
    base_url = request.form.get("ai_base_url", "").strip()
    model = request.form.get("ai_model", "").strip()
    api_key = request.form.get("ai_api_key", "").strip()

    # Only overwrite the stored key if a new value was typed.
    rows = db.query("SELECT value FROM settings WHERE key=%s"
                    if db.engine == "mysql" else
                    "SELECT value FROM settings WHERE key=?", ("ai_api_key",))
    if not api_key and rows:
        api_key = rows[0]["value"]

    _save_setting("ai_provider", provider)
    _save_setting("ai_base_url", base_url)
    _save_setting("ai_model", model)
    _save_setting("ai_api_key", api_key)
    flash("AI provider settings saved.")
    return redirect(url_for("settings_page"))


def _save_setting(key, value):
    if db.engine == "mysql":
        db.execute("INSERT INTO settings (`key`, value) VALUES (%s,%s) "
                   "ON DUPLICATE KEY UPDATE value=%s", (key, value, value))
    else:
        db.execute("INSERT INTO settings (key, value) VALUES (?,?) "
                   "ON CONFLICT(key) DO UPDATE SET value=?",
                   (key, value, value))


@app.route("/settings/test", methods=["POST"])
def settings_test():
    provider_name = request.form.get("ai_provider", "mock").strip().lower()
    base_url = request.form.get("ai_base_url", config.AI_BASE_URL).strip()
    model = request.form.get("ai_model", config.AI_MODEL).strip()
    api_key = request.form.get("ai_api_key", "").strip()
    if not api_key:
        rows = db.query("SELECT value FROM settings WHERE key=%s"
                        if db.engine == "mysql" else
                        "SELECT value FROM settings WHERE key=?", ("ai_api_key",))
        api_key = rows[0]["value"] if rows else config.AI_API_KEY
    provider = get_provider(provider_name, base_url, api_key, model)
    ok, message = provider.health_check()
    return jsonify({"ok": ok, "message": message, "provider": provider.name})


def mask_key(key):
    if not key:
        return ""
    if len(key) <= 8:
        return "•" * len(key)
    return key[:4] + "•" * 8 + key[-4:]


@app.route("/agents")
def agents():
    summary = get_recon_summary()
    return render_template("agents.html", summary=summary)


@app.route("/health")
def health():
    return jsonify({"ok": True, "provider": current_provider_label()})


if __name__ == "__main__":
    # Dev server only. Production uses Passenger/WSGI (passenger_wsgi.py).
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)