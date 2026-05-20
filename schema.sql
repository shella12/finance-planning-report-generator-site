PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    is_married INTEGER NOT NULL DEFAULT 0,

    client1_name TEXT NOT NULL,
    client1_dob TEXT NOT NULL,
    client1_ssn_last4 TEXT,

    client2_name TEXT,
    client2_dob TEXT,
    client2_ssn_last4 TEXT,

    monthly_salary REAL NOT NULL DEFAULT 0,
    client1_salary REAL NOT NULL DEFAULT 0,
    client2_salary REAL NOT NULL DEFAULT 0,
    monthly_expense_budget REAL NOT NULL DEFAULT 0,
    private_reserve_target_override REAL,

    trust_property_address TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('retirement', 'non_retirement', 'liability')),
    owner TEXT NOT NULL CHECK (owner IN ('client1', 'client2', 'joint')),
    account_type TEXT NOT NULL,
    nickname TEXT,
    account_number_last4 TEXT,
    interest_rate REAL,
    institution TEXT,
    is_investment INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS insurance_deductibles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    amount REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    report_date TEXT NOT NULL,
    inflow_monthly REAL,
    outflow_monthly REAL,
    private_reserve_balance REAL,
    investment_account_balance REAL,
    trust_zillow_value REAL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'finalized')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    finalized_at TEXT,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS account_balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    balance REAL,
    cash_balance REAL,
    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
    UNIQUE (report_id, account_id)
);

CREATE INDEX IF NOT EXISTS idx_accounts_client ON accounts(client_id);
CREATE INDEX IF NOT EXISTS idx_deductibles_client ON insurance_deductibles(client_id);
CREATE INDEX IF NOT EXISTS idx_reports_client ON reports(client_id);
CREATE INDEX IF NOT EXISTS idx_balances_report ON account_balances(report_id);
