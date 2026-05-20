"""Seed an example client mirroring the sample TCC layout from the call.

Run:  python3 seed.py
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import db as dbmod

DB_PATH = Path(__file__).parent / "portal.db"


def seed():
    if DB_PATH.exists():
        DB_PATH.unlink()
    dbmod.init_db(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        cur = conn.cursor()

        # ---------------- client ----------------
        cur.execute(
            """
            INSERT INTO clients (
                label, is_married,
                client1_name, client1_dob, client1_ssn_last4,
                client2_name, client2_dob, client2_ssn_last4,
                monthly_salary, monthly_expense_budget,
                trust_property_address
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "The Example Family",
                1,
                "Alex Example", "1978-04-12", "1234",
                "Jordan Example", "1980-09-03", "5678",
                15000, 12000,
                "742 Evergreen Terrace, Atlanta, GA",
            ),
        )
        client_id = cur.lastrowid

        # ---------------- accounts ----------------
        accounts = [
            # Client 1 retirement (2 accounts, per the sample)
            ("retirement",    "client1", "Roth IRA",        "Vanguard",    "9821", None, "Vanguard",     1),
            ("retirement",    "client1", "Traditional IRA", "Fidelity",    "4410", None, "Fidelity",     1),
            # Client 2 retirement (3 accounts)
            ("retirement",    "client2", "401K",            "T. Rowe Price","2207", None, "T. Rowe Price",1),
            ("retirement",    "client2", "Roth IRA",        "Vanguard",    "9911", None, "Vanguard",     1),
            ("retirement",    "client2", "Pension",         "State of GA", "3015", None, "State of GA",  0),
            # Non-retirement — joint
            ("non_retirement","joint",   "Brokerage",       "Schwab Brokerage", "6633", None, "Charles Schwab", 1),
            ("non_retirement","joint",   "Checking",        "Pinnacle Inflow",  "1101", None, "Pinnacle Bank",  0),
            ("non_retirement","joint",   "Checking",        "Pinnacle Outflow", "1102", None, "Pinnacle Bank",  0),
            ("non_retirement","joint",   "High-Yield Savings","Private Reserve","1103", None, "Pinnacle Bank",  0),
            # Non-retirement — Client 1 solo (stock options example from call)
            ("non_retirement","client1", "Stock Options",   "E-Trade",     "7755", None, "E-Trade",        1),
            # Liabilities
            ("liability",     "joint",   "Mortgage",        "Primary residence","",   3.250, "Wells Fargo",  0),
            ("liability",     "joint",   "Auto Loan",       "Subaru Outback",   "",   5.490, "Capital One",  0),
        ]
        for i, a in enumerate(accounts):
            cat, owner, atype, nickname, last4, rate, institution, is_inv = a
            cur.execute(
                """INSERT INTO accounts
                   (client_id, category, owner, account_type, nickname, account_number_last4,
                    interest_rate, institution, is_investment, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (client_id, cat, owner, atype, nickname, last4, rate, institution, is_inv, i),
            )

        # ---------------- deductibles ----------------
        for label, amount in [("Car", 1000), ("Home", 2000), ("Health", 1000)]:
            cur.execute(
                "INSERT INTO insurance_deductibles (client_id, label, amount) VALUES (?, ?, ?)",
                (client_id, label, amount),
            )

        # ---------------- previous-quarter report (so "use last" chips have values) ----------------
        cur.execute(
            """INSERT INTO reports
               (client_id, report_date, inflow_monthly, outflow_monthly,
                private_reserve_balance, investment_account_balance, trust_zillow_value,
                status, finalized_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'finalized', CURRENT_TIMESTAMP)""",
            (client_id, "2026-02-15", 15000, 12000, 70000, 14500, 445000),
        )
        prev_report_id = cur.lastrowid

        # Account balances for previous quarter
        cur.execute("SELECT id, category, owner, account_type FROM accounts WHERE client_id = ?", (client_id,))
        rows = cur.fetchall()
        # Plausible balances mirroring the call ($11K Roth, etc.)
        balance_by_type = {
            "Roth IRA": [10100.50, 9450.25],
            "Traditional IRA": [22300.00],
            "401K": [148500.00],
            "Pension": [62000.00],
            "Brokerage": [50250.00],
            "Checking": [3200.00, 8400.00],
            "High-Yield Savings": [70000.00],
            "Stock Options": [125000.00],
            "Mortgage": [245000.00],
            "Auto Loan": [18500.00],
        }
        type_use_count = {k: 0 for k in balance_by_type}
        for r in rows:
            acct_id, cat, owner, atype = r
            options = balance_by_type.get(atype, [0])
            idx = type_use_count[atype]
            bal = options[idx % len(options)]
            type_use_count[atype] += 1
            cash = None
            if atype in ("Roth IRA", "Traditional IRA", "Brokerage", "Stock Options"):
                cash = round(bal * 0.04, 2)
            cur.execute(
                "INSERT INTO account_balances (report_id, account_id, balance, cash_balance) VALUES (?, ?, ?, ?)",
                (prev_report_id, acct_id, bal, cash),
            )

        conn.commit()
        print(f"Seeded client #{client_id} ({rows.__len__()} accounts) and 1 prior-quarter report (#{prev_report_id}).")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
