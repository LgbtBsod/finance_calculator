-- index idx_debt_repayments_debt_id
CREATE INDEX idx_debt_repayments_debt_id ON debt_repayments(debt_id);

-- index idx_expenses_year_month
CREATE INDEX idx_expenses_year_month ON expenses(year, month);

-- index idx_income_year_month
CREATE INDEX idx_income_year_month ON income(year, month);

-- table birthdays
CREATE TABLE birthdays (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    NOT NULL,
                    birth_date  TEXT    NOT NULL,
                    gift_amount REAL    NOT NULL DEFAULT 0.0
                );

-- table calendar_corrections
CREATE TABLE calendar_corrections (
                    date      TEXT PRIMARY KEY,
                    kind      TEXT NOT NULL,
                    source    TEXT NOT NULL
                );

-- table calendar_data
CREATE TABLE calendar_data (
                    date         TEXT PRIMARY KEY,
                    is_working   INTEGER NOT NULL DEFAULT 1,
                    is_holiday   INTEGER NOT NULL DEFAULT 0,
                    is_shortened INTEGER NOT NULL DEFAULT 0
                );

-- table debt_repayments
CREATE TABLE debt_repayments (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    debt_id   INTEGER NOT NULL,
                    amount    REAL    NOT NULL DEFAULT 0.0,
                    date      TEXT    NOT NULL,
                    note      TEXT,
                    FOREIGN KEY (debt_id) REFERENCES debts(id) ON DELETE CASCADE
                );

-- table debts
CREATE TABLE debts (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    title           TEXT    NOT NULL,
                    total_amount    REAL    NOT NULL DEFAULT 0.0,
                    month           INTEGER NOT NULL,
                    year            INTEGER NOT NULL,
                    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
                    monthly_payment REAL    NOT NULL DEFAULT 0,
                    payment_half    INTEGER NOT NULL DEFAULT 2
                );

-- table expense_groups
CREATE TABLE expense_groups (
                    id            TEXT    PRIMARY KEY,
                    name          TEXT    NOT NULL,
                    color         TEXT    NOT NULL,
                    parent_id     TEXT,
                    sort_order    INTEGER NOT NULL DEFAULT 0,
                    monthly_limit REAL
                );

-- table expenses
CREATE TABLE expenses (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    name          TEXT    NOT NULL,
                    amount        REAL    NOT NULL DEFAULT 0.0,
                    half          INTEGER NOT NULL DEFAULT 1,
                    month         INTEGER NOT NULL,
                    year          INTEGER NOT NULL,
                    is_recurring  INTEGER NOT NULL DEFAULT 0,
                    is_inclusive  INTEGER NOT NULL DEFAULT 0,
                    group_id      TEXT, recurring_until TEXT,
                    FOREIGN KEY (group_id) REFERENCES expense_groups(id)
                );

-- table income
CREATE TABLE income (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    name              TEXT    NOT NULL,
                    amount            REAL    NOT NULL DEFAULT 0.0,
                    half              INTEGER NOT NULL DEFAULT 1,
                    month             INTEGER NOT NULL,
                    year              INTEGER NOT NULL,
                    is_recurring      INTEGER NOT NULL DEFAULT 0,
                    recurring_until   TEXT,
                    kind              TEXT    NOT NULL DEFAULT 'fixed',
                    kef               REAL,
                    split_method      TEXT,
                    first_half_ratio  REAL,
                    second_half_ratio REAL
                );

-- table period_overrides
CREATE TABLE period_overrides (
                    kind    TEXT    NOT NULL,
                    row_id  INTEGER NOT NULL,
                    year    INTEGER NOT NULL,
                    month   INTEGER NOT NULL,
                    amount  REAL    NOT NULL,
                    PRIMARY KEY (kind, row_id, year, month)
                );

-- table settings
CREATE TABLE settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

-- table sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);

-- table vacations
CREATE TABLE vacations (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_amount REAL    NOT NULL DEFAULT 0.0,
                    payout_date  TEXT,
                    start_date   TEXT,
                    end_date     TEXT
                );

