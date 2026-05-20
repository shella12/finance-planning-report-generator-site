"""AW Client Report Portal — Flask entry point.

Run locally:
    python3 app.py
Then open http://127.0.0.1:5050.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, send_file, url_for

import db as dbmod
from calculations import (
    AccountBalance,
    SACSResult,
    TCCResult,
    calc_age,
    compute_sacs,
    compute_tcc,
)


APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "portal.db"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["DATABASE_PATH"] = str(DB_PATH)
    app.config["SECRET_KEY"] = "demo-not-a-real-secret"

    if not DB_PATH.exists():
        dbmod.init_db(DB_PATH)

    app.teardown_appcontext(dbmod.close_db)

    @app.template_filter("usd")
    def usd(value):
        if value is None or value == "":
            return "—"
        try:
            return f"${float(value):,.2f}"
        except (TypeError, ValueError):
            return value

    @app.template_filter("usd0")
    def usd0(value):
        if value is None or value == "":
            return "—"
        try:
            return f"${float(value):,.0f}"
        except (TypeError, ValueError):
            return value

    @app.template_filter("pct")
    def pct(value):
        if value is None or value == "":
            return "—"
        try:
            return f"{float(value):.3f}%"
        except (TypeError, ValueError):
            return value

    register_routes(app)
    return app


# ---------------- helpers ----------------

def get_client_or_404(client_id: int):
    c = dbmod.query("SELECT * FROM clients WHERE id = ?", (client_id,), one=True)
    if not c:
        abort(404)
    return c


def get_accounts(client_id: int):
    return dbmod.query(
        "SELECT * FROM accounts WHERE client_id = ? ORDER BY category, owner, sort_order, id",
        (client_id,),
    )


def get_deductibles(client_id: int):
    return dbmod.query(
        "SELECT * FROM insurance_deductibles WHERE client_id = ? ORDER BY id",
        (client_id,),
    )


def get_reports(client_id: int):
    return dbmod.query(
        "SELECT * FROM reports WHERE client_id = ? ORDER BY report_date DESC, id DESC",
        (client_id,),
    )


def get_report_balances(report_id: int):
    return dbmod.query(
        "SELECT * FROM account_balances WHERE report_id = ?",
        (report_id,),
    )


def last_report_for(client_id: int, before_report_id: int | None = None):
    if before_report_id:
        return dbmod.query(
            "SELECT * FROM reports WHERE client_id = ? AND id < ? ORDER BY id DESC LIMIT 1",
            (client_id, before_report_id),
            one=True,
        )
    return dbmod.query(
        "SELECT * FROM reports WHERE client_id = ? ORDER BY id DESC LIMIT 1",
        (client_id,),
        one=True,
    )


def parse_float(v):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except ValueError:
        return None


def build_account_balances(client_id: int, balances_by_account: dict[int, dict]) -> list[AccountBalance]:
    accounts = get_accounts(client_id)
    result = []
    for a in accounts:
        b = balances_by_account.get(a["id"], {})
        result.append(
            AccountBalance(
                account_id=a["id"],
                category=a["category"],
                owner=a["owner"],
                balance=b.get("balance") or 0,
                cash_balance=b.get("cash_balance"),
                interest_rate=a["interest_rate"],
                account_type=a["account_type"],
                nickname=a["nickname"] or "",
                account_number_last4=a["account_number_last4"] or "",
            )
        )
    return result


REQUIRED_REPORT_FIELDS = (
    "inflow_monthly",
    "outflow_monthly",
    "private_reserve_balance",
    "investment_account_balance",
    "trust_zillow_value",
)


def is_report_complete(report: dict, accounts, balances_by_account: dict[int, dict]) -> bool:
    """A report is complete when every required cashflow field has a value
    and every account on the client has a balance entry for this report.
    Cash-balance subfields are optional; only the headline balance is required.
    """
    for field in REQUIRED_REPORT_FIELDS:
        if report.get(field) is None:
            return False
    for a in accounts:
        b = balances_by_account.get(a["id"], {})
        if b.get("balance") is None:
            return False
    return True


def compute_report_results(client_id: int, report: dict, balances_by_account: dict[int, dict]):
    client = get_client_or_404(client_id)
    deductibles = get_deductibles(client_id)
    deductible_total = sum(d["amount"] for d in deductibles)

    sacs = compute_sacs(
        inflow=report.get("inflow_monthly") or 0,
        outflow=report.get("outflow_monthly") or 0,
        monthly_expense_budget=client["monthly_expense_budget"],
        insurance_deductibles_total=deductible_total,
        private_reserve_balance=report.get("private_reserve_balance") or 0,
        investment_account_balance=report.get("investment_account_balance") or 0,
        private_reserve_target_override=client["private_reserve_target_override"],
    )

    account_balances = build_account_balances(client_id, balances_by_account)
    tcc = compute_tcc(account_balances, trust_value=report.get("trust_zillow_value") or 0)

    # Split non-retirement accounts into left/right columns for the TCC layout:
    # owner=='client1' → left, owner=='client2' → right, joint → alternate to balance.
    nr_left, nr_right = [], []
    for b in tcc.non_retirement:
        if b.owner == "client1":
            nr_left.append(b)
        elif b.owner == "client2":
            nr_right.append(b)
        else:
            (nr_left if len(nr_left) <= len(nr_right) else nr_right).append(b)
    tcc.non_retirement_left = nr_left
    tcc.non_retirement_right = nr_right
    # Same split for retirement (per-spouse already filtered, but mirror the attribute names)
    tcc.retirement_left = tcc.retirement_client1
    tcc.retirement_right = tcc.retirement_client2

    return client, deductibles, sacs, tcc, account_balances


# ---------------- routes ----------------

def register_routes(app: Flask):
    @app.route("/")
    def index():
        rows = dbmod.query(
            """
            SELECT c.*, (
                SELECT MAX(r.report_date) FROM reports r WHERE r.client_id = c.id
            ) AS last_report_date
            FROM clients c
            ORDER BY c.label
            """
        )
        return render_template("index.html", clients=rows)

    @app.route("/clients/new", methods=["GET", "POST"])
    def client_new():
        if request.method == "POST":
            return save_client(None)
        return render_template("client_form.html", client=None, accounts=[], deductibles=[])

    @app.route("/clients/<int:client_id>")
    def client_detail(client_id):
        client = get_client_or_404(client_id)
        accounts = get_accounts(client_id)
        deductibles = get_deductibles(client_id)
        reports = get_reports(client_id)
        return render_template(
            "client_detail.html",
            client=client,
            accounts=accounts,
            deductibles=deductibles,
            reports=reports,
            calc_age=calc_age,
        )

    @app.route("/clients/<int:client_id>/edit", methods=["GET", "POST"])
    def client_edit(client_id):
        client = get_client_or_404(client_id)
        if request.method == "POST":
            return save_client(client_id)
        return render_template(
            "client_form.html",
            client=client,
            accounts=get_accounts(client_id),
            deductibles=get_deductibles(client_id),
        )

    @app.route("/clients/<int:client_id>/delete", methods=["POST"])
    def client_delete(client_id):
        get_client_or_404(client_id)
        dbmod.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        flash("Client deleted.")
        return redirect(url_for("index"))

    @app.route("/clients/<int:client_id>/reports/new", methods=["GET", "POST"])
    def report_new(client_id):
        client = get_client_or_404(client_id)
        accounts = get_accounts(client_id)
        last = last_report_for(client_id)
        last_balances = {b["account_id"]: dict(b) for b in (get_report_balances(last["id"]) if last else [])}

        if request.method == "POST":
            return save_report(client_id, None)

        return render_template(
            "report_form.html",
            client=client,
            accounts=accounts,
            deductibles=get_deductibles(client_id),
            report=None,
            balances={},
            last_report=last,
            last_balances=last_balances,
            today=date.today().isoformat(),
        )

    @app.route("/reports/<int:report_id>/edit", methods=["GET", "POST"])
    def report_edit(report_id):
        report = dbmod.query("SELECT * FROM reports WHERE id = ?", (report_id,), one=True)
        if not report:
            abort(404)
        client = get_client_or_404(report["client_id"])
        accounts = get_accounts(client["id"])
        balances = {b["account_id"]: dict(b) for b in get_report_balances(report_id)}
        last = last_report_for(client["id"], before_report_id=report_id)
        last_balances = {b["account_id"]: dict(b) for b in (get_report_balances(last["id"]) if last else [])}

        if request.method == "POST":
            return save_report(client["id"], report_id)

        return render_template(
            "report_form.html",
            client=client,
            accounts=accounts,
            deductibles=get_deductibles(client["id"]),
            report=report,
            balances=balances,
            last_report=last,
            last_balances=last_balances,
            today=report["report_date"],
        )

    @app.route("/reports/<int:report_id>")
    def report_view(report_id):
        report = dbmod.query("SELECT * FROM reports WHERE id = ?", (report_id,), one=True)
        if not report:
            abort(404)
        accounts = get_accounts(report["client_id"])
        balances = {b["account_id"]: dict(b) for b in get_report_balances(report_id)}
        client, deductibles, sacs, tcc, _ = compute_report_results(report["client_id"], dict(report), balances)
        complete = is_report_complete(dict(report), accounts, balances)
        return render_template(
            "report_view.html",
            client=client,
            report=report,
            sacs=sacs,
            tcc=tcc,
            deductibles=deductibles,
            is_complete=complete,
            calc_age=calc_age,
        )

    @app.route("/reports/<int:report_id>/delete", methods=["POST"])
    def report_delete(report_id):
        report = dbmod.query("SELECT client_id FROM reports WHERE id = ?", (report_id,), one=True)
        if not report:
            abort(404)
        client_id = report["client_id"]
        dbmod.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        flash("Report deleted.")
        return redirect(url_for("client_detail", client_id=client_id))

    @app.route("/reports/<int:report_id>/pdf/<kind>")
    def report_pdf(report_id, kind):
        if kind not in ("sacs", "tcc"):
            abort(404)
        report = dbmod.query("SELECT * FROM reports WHERE id = ?", (report_id,), one=True)
        if not report:
            abort(404)
        accounts = get_accounts(report["client_id"])
        balances = {b["account_id"]: dict(b) for b in get_report_balances(report_id)}
        if not is_report_complete(dict(report), accounts, balances):
            abort(400, description="Report has missing required values.")
        client, deductibles, sacs, tcc, _ = compute_report_results(
            report["client_id"], dict(report), balances
        )
        import pdf_generator
        pdf_bytes = pdf_generator.render(
            kind=kind,
            client=client,
            report=report,
            sacs=sacs,
            tcc=tcc,
            deductibles=deductibles,
        )
        safe_name = (client["label"] or "client").replace(" ", "_")
        filename = f"{safe_name}_{kind.upper()}_{report['report_date']}.pdf"
        inline = request.args.get("inline") == "1"
        from io import BytesIO
        return send_file(
            BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=not inline,
            download_name=filename,
        )


# ---------------- form persistence ----------------

def save_client(client_id: int | None):
    f = request.form
    is_married = 1 if f.get("is_married") == "on" else 0
    client1_salary = parse_float(f.get("client1_salary")) or 0
    client2_salary = (parse_float(f.get("client2_salary")) or 0) if is_married else 0
    fields = dict(
        label=f.get("label", "").strip() or "Untitled client",
        is_married=is_married,
        client1_name=f.get("client1_name", "").strip(),
        client1_dob=f.get("client1_dob", "").strip(),
        client1_ssn_last4=f.get("client1_ssn_last4", "").strip() or None,
        client2_name=f.get("client2_name", "").strip() or None if is_married else None,
        client2_dob=f.get("client2_dob", "").strip() or None if is_married else None,
        client2_ssn_last4=(f.get("client2_ssn_last4", "").strip() or None) if is_married else None,
        monthly_salary=client1_salary + client2_salary,
        client1_salary=client1_salary,
        client2_salary=client2_salary,
        monthly_expense_budget=parse_float(f.get("monthly_expense_budget")) or 0,
        private_reserve_target_override=parse_float(f.get("private_reserve_target_override")),
        trust_property_address=f.get("trust_property_address", "").strip() or None,
    )

    if client_id is None:
        cols = ", ".join(fields.keys())
        ph = ", ".join("?" for _ in fields)
        client_id = dbmod.execute(
            f"INSERT INTO clients ({cols}) VALUES ({ph})", tuple(fields.values())
        )
    else:
        sets = ", ".join(f"{k} = ?" for k in fields)
        dbmod.execute(
            f"UPDATE clients SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (*fields.values(), client_id),
        )

    # Replace accounts + deductibles wholesale on save (simpler than diffing).
    dbmod.execute("DELETE FROM accounts WHERE client_id = ?", (client_id,))
    dbmod.execute("DELETE FROM insurance_deductibles WHERE client_id = ?", (client_id,))

    # Account rows arrive as parallel lists: acct_category[], acct_owner[], etc.
    cats = f.getlist("acct_category[]")
    owners = f.getlist("acct_owner[]")
    types = f.getlist("acct_type[]")
    nicks = f.getlist("acct_nickname[]")
    lasts = f.getlist("acct_last4[]")
    rates = f.getlist("acct_rate[]")
    institutions = f.getlist("acct_institution[]")
    investments = f.getlist("acct_is_investment[]")

    for i, cat in enumerate(cats):
        if not cat:
            continue
        owner = owners[i] if i < len(owners) else "joint"
        atype = types[i] if i < len(types) else ""
        if not atype.strip():
            continue
        dbmod.execute(
            """
            INSERT INTO accounts (
                client_id, category, owner, account_type, nickname,
                account_number_last4, interest_rate, institution, is_investment, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                client_id,
                cat,
                owner,
                atype.strip(),
                (nicks[i].strip() if i < len(nicks) and nicks[i] else None),
                (lasts[i].strip() if i < len(lasts) and lasts[i] else None),
                parse_float(rates[i]) if i < len(rates) and rates[i] else None,
                (institutions[i].strip() if i < len(institutions) and institutions[i] else None),
                1 if (i < len(investments) and investments[i] == "1") else 0,
                i,
            ),
        )

    # Deductibles
    d_labels = f.getlist("ded_label[]")
    d_amounts = f.getlist("ded_amount[]")
    for i, label in enumerate(d_labels):
        if not label.strip():
            continue
        amt = parse_float(d_amounts[i]) if i < len(d_amounts) else None
        if amt is None:
            continue
        dbmod.execute(
            "INSERT INTO insurance_deductibles (client_id, label, amount) VALUES (?, ?, ?)",
            (client_id, label.strip(), amt),
        )

    flash("Client saved.")
    return redirect(url_for("client_detail", client_id=client_id))


def save_report(client_id: int, report_id: int | None):
    f = request.form
    fields = dict(
        client_id=client_id,
        report_date=f.get("report_date") or date.today().isoformat(),
        inflow_monthly=parse_float(f.get("inflow_monthly")),
        outflow_monthly=parse_float(f.get("outflow_monthly")),
        private_reserve_balance=parse_float(f.get("private_reserve_balance")),
        investment_account_balance=parse_float(f.get("investment_account_balance")),
        trust_zillow_value=parse_float(f.get("trust_zillow_value")),
        status=f.get("status") or "draft",
    )

    if report_id is None:
        cols = ", ".join(fields.keys())
        ph = ", ".join("?" for _ in fields)
        report_id = dbmod.execute(
            f"INSERT INTO reports ({cols}) VALUES ({ph})", tuple(fields.values())
        )
    else:
        sets = ", ".join(f"{k} = ?" for k in fields if k != "client_id")
        vals = [v for k, v in fields.items() if k != "client_id"]
        dbmod.execute(
            f"UPDATE reports SET {sets} WHERE id = ?",
            (*vals, report_id),
        )

    accounts = get_accounts(client_id)
    for a in accounts:
        bal = parse_float(f.get(f"bal_{a['id']}"))
        cash = parse_float(f.get(f"cash_{a['id']}"))
        existing = dbmod.query(
            "SELECT id FROM account_balances WHERE report_id = ? AND account_id = ?",
            (report_id, a["id"]),
            one=True,
        )
        if existing:
            dbmod.execute(
                "UPDATE account_balances SET balance = ?, cash_balance = ? WHERE id = ?",
                (bal, cash, existing["id"]),
            )
        else:
            dbmod.execute(
                "INSERT INTO account_balances (report_id, account_id, balance, cash_balance) VALUES (?, ?, ?, ?)",
                (report_id, a["id"], bal, cash),
            )

    flash("Report saved.")
    return redirect(url_for("report_view", report_id=report_id))


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5050))
    debug = os.environ.get("FLASK_DEBUG") == "1"
    create_app().run(host="0.0.0.0", port=port, debug=debug)
