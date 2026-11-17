"""Synthetic-database helpers for pilot refresh tests. Synthetic data only."""
from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"



def make_db(path, *, filings=None, structured_rules=None, funds=None, share_classes=None):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE filings (
            filing_id INTEGER PRIMARY KEY,
            form_type TEXT,
            accession TEXT,
            filing_date TEXT,
            edgar_url TEXT
        );
        CREATE TABLE funds (
            fund_id INTEGER PRIMARY KEY,
            cik TEXT,
            series_id TEXT,
            fund_name TEXT,
            family TEXT
        );
        CREATE TABLE share_classes (
            class_id INTEGER PRIMARY KEY,
            fund_id INTEGER,
            ticker TEXT,
            class_name TEXT,
            class_contract_id TEXT
        );
        CREATE TABLE structured_rules (
            rule_id INTEGER PRIMARY KEY,
            category TEXT,
            description TEXT,
            condition_text TEXT,
            source_snippet TEXT,
            ticker TEXT,
            fund_family TEXT,
            accession TEXT,
            form_type TEXT,
            filing_date TEXT,
            intermediary TEXT,
            status TEXT
        );
        CREATE TABLE waiver_rules (
            rule_id INTEGER PRIMARY KEY
        );
        """
    )
    if funds:
        conn.executemany(
            "INSERT INTO funds(fund_id, cik, series_id, fund_name, family) VALUES (?,?,?,?,?)",
            funds,
        )
    if share_classes:
        conn.executemany(
            "INSERT INTO share_classes(class_id, fund_id, ticker, class_name, class_contract_id) VALUES (?,?,?,?,?)",
            share_classes,
        )
    if filings:
        conn.executemany(
            "INSERT INTO filings(filing_id, form_type, accession, filing_date, edgar_url) VALUES (?,?,?,?,?)",
            filings,
        )
    if structured_rules:
        conn.executemany(
            """INSERT INTO structured_rules(
                rule_id, category, description, condition_text, source_snippet,
                ticker, fund_family, accession, form_type, filing_date, intermediary, status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            structured_rules,
        )
    conn.commit()
    conn.close()
    return path
