import os
import sqlite3
from datetime import datetime

def get_db_path() -> str:
    """
    Reads the environment variable COINTOOLS_DB_PATH for the SQLite file.
    Raises an error if not set.
    """
    db_path = os.environ.get('COINTOOLS_DB_PATH')
    if not db_path:
        raise EnvironmentError("Environment variable COINTOOLS_DB_PATH is required but not set.")
    return db_path

def init_db():
    """
    Initializes the SQLite database if it doesn't already exist.
    Creates the tables if they don't exist.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            public_key TEXT NOT NULL,
            private_key_encrypted BLOB NOT NULL,
            status TEXT NOT NULL,
            last_accessed_timestamp TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickers (
            ca TEXT PRIMARY KEY,
            coin TEXT NOT NULL,
            ticker TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()

def get_all_wallets():
    """
    Returns a list of all wallets in DB as dictionaries
    with keys: id, public_key, private_key_encrypted, status, last_accessed_timestamp.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM wallets")
    rows = cursor.fetchall()
    conn.close()

    # Convert to list of dicts
    return [dict(row) for row in rows]

def get_wallet_by_id(wallet_id: int):
    """
    Returns a single wallet by ID or None if not found.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM wallets WHERE id=?", (wallet_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None

def update_wallet_access_time(wallet_id: int):
    """
    Updates the 'last_accessed_timestamp' for the given wallet ID.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE wallets SET last_accessed_timestamp=? WHERE id=?",
        (str(datetime.now()), wallet_id)
    )
    conn.commit()
    conn.close()

def update_name(wallet_id: int, name: str):
    """
    Updates the 'name' for the given wallet ID.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE wallets SET name=? WHERE id=?",
        (name, wallet_id)
    )
    conn.commit()
    conn.close()

def insert_wallet(name: str, public_key: str, private_key_encrypted: bytes):
    """
    Inserts a new wallet record into the `wallets` table.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO wallets (name, public_key, private_key_encrypted, status, last_accessed_timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        name,
        public_key,
        private_key_encrypted,
        'active',
        str(datetime.now())
    ))
    wallet_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return wallet_id

def get_tickers():
    """
    Returns a list of all tickers in DB as a dictionary
    ca -> (coin, ticker).
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tickers")
    rows = cursor.fetchall()
    conn.close()

    # Convert to dict
    tickers = {}
    for row in rows:
        tickers[row['ca']] = (row['coin'], row['ticker'])
    return tickers

def upsert_ticker(ca: str, coin: str, ticker: str):
    """
    Inserts or updates a ticker record in the `tickers` table.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO tickers (ca, coin, ticker)
        VALUES (?, ?, ?)
        ON CONFLICT(ca) DO UPDATE SET coin=excluded.coin, ticker=excluded.ticker        
    ''', (ca, coin, ticker))
    conn.commit()
    conn.close()
    