"""Pure functions for all SACS/TCC math. No DB, no Flask — just numbers in, numbers out.

Calculation rules confirmed in the call (Rebecca, 24:14-26:32):
- SACS excess = inflow - outflow.
- Private Reserve target = 6 * monthly_expenses + sum(insurance_deductibles).
- TCC retirement totals are per-spouse (sum of that spouse's retirement accounts).
- TCC non-retirement total = sum of all non-retirement accounts. Trust is NOT added in.
- Grand total net worth = client1_retirement + client2_retirement + non_retirement + trust.
- Liabilities are shown separately and NOT subtracted from net worth.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class AccountBalance:
    account_id: int
    category: str          # 'retirement' | 'non_retirement' | 'liability'
    owner: str             # 'client1' | 'client2' | 'joint'
    balance: float = 0.0
    cash_balance: float | None = None
    interest_rate: float | None = None
    account_type: str = ""
    nickname: str = ""
    account_number_last4: str = ""


@dataclass
class SACSResult:
    inflow: float
    outflow: float
    excess: float
    private_reserve_target: float
    private_reserve_balance: float
    investment_account_balance: float


@dataclass
class TCCResult:
    client1_retirement_total: float
    client2_retirement_total: float
    non_retirement_total: float
    trust_value: float
    liabilities_total: float
    grand_total_net_worth: float
    retirement_client1: list[AccountBalance] = field(default_factory=list)
    retirement_client2: list[AccountBalance] = field(default_factory=list)
    non_retirement: list[AccountBalance] = field(default_factory=list)
    liabilities: list[AccountBalance] = field(default_factory=list)


def compute_sacs(
    inflow: float,
    outflow: float,
    monthly_expense_budget: float,
    insurance_deductibles_total: float,
    private_reserve_balance: float,
    investment_account_balance: float,
    private_reserve_target_override: float | None = None,
) -> SACSResult:
    excess = (inflow or 0) - (outflow or 0)
    if private_reserve_target_override is not None:
        target = private_reserve_target_override
    else:
        target = 6 * (monthly_expense_budget or 0) + (insurance_deductibles_total or 0)
    return SACSResult(
        inflow=inflow or 0,
        outflow=outflow or 0,
        excess=excess,
        private_reserve_target=target,
        private_reserve_balance=private_reserve_balance or 0,
        investment_account_balance=investment_account_balance or 0,
    )


def compute_tcc(
    balances: Iterable[AccountBalance],
    trust_value: float,
) -> TCCResult:
    bals = list(balances)
    retirement_c1 = [b for b in bals if b.category == "retirement" and b.owner == "client1"]
    retirement_c2 = [b for b in bals if b.category == "retirement" and b.owner == "client2"]
    non_retirement = [b for b in bals if b.category == "non_retirement"]
    liabilities = [b for b in bals if b.category == "liability"]

    c1_total = sum(b.balance for b in retirement_c1)
    c2_total = sum(b.balance for b in retirement_c2)
    nr_total = sum(b.balance for b in non_retirement)
    liab_total = sum(b.balance for b in liabilities)

    # Net worth: trust IS added, liabilities are NOT subtracted (call 26:17-22).
    grand_total = c1_total + c2_total + nr_total + (trust_value or 0)

    return TCCResult(
        client1_retirement_total=c1_total,
        client2_retirement_total=c2_total,
        non_retirement_total=nr_total,
        trust_value=trust_value or 0,
        liabilities_total=liab_total,
        grand_total_net_worth=grand_total,
        retirement_client1=retirement_c1,
        retirement_client2=retirement_c2,
        non_retirement=non_retirement,
        liabilities=liabilities,
    )


def calc_age(dob_iso: str, as_of_iso: str | None = None) -> int | None:
    from datetime import date
    if not dob_iso:
        return None
    try:
        dob = date.fromisoformat(dob_iso)
    except ValueError:
        return None
    today = date.fromisoformat(as_of_iso) if as_of_iso else date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
