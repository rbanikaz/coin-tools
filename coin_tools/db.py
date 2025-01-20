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
        CREATE TABLE IF NOT EXISTS token_metadata (
            ca TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            uri TEXT,
            decimals INTEGER
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

    cursor.execute("SELECT * FROM wallets where status <> 'deleted'")
    rows = cursor.fetchall()
    conn.close()

    # Convert to list of dicts
    return [dict(row) for row in rows]

def get_wallets_by_name_prefix(name: str):
    """
    Returns a list of all wallets in DB as dictionaries searching by name (case insensitive prefix).
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM wallets where status <> 'deleted' and lower(name) like ?", (f"{name.lower()}%",))
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

def update_private_key(wallet_id: int, private_key_encrypted: bytes):
    """
    Updates the 'private_key_encrypted' for the given wallet ID.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE wallets SET private_key_encrypted=? WHERE id=?",
        (private_key_encrypted, wallet_id)
    )
    conn.commit()
    conn.close()

def update_wallet_status(wallet_id: int, status: str):
    """
    Updates the 'status' for the given wallet ID.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE wallets SET status=? WHERE id=?",
        (status, wallet_id)
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

def get_token_metadata():
    """
    Returns a list of all tokens in DB as a dictionary
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM token_metadata")
    rows = cursor.fetchall()
    conn.close()

    # Convert to dict
    tokens = {}
    for row in rows:
        tokens[row['ca']] = dict(row)
    return tokens

def upsert_token_metadata(ca: str, coin: str, ticker: str, uri: str, decimals: int):
    """
    Inserts or updates a token_metadata record in the `token_metadata` table.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO token_metadata (ca, name, symbol, uri, decimals)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(ca) DO UPDATE SET name=excluded.name, symbol=excluded.symbol, uri=excluded.uri, decimals=excluded.decimals     
    ''', (ca, coin, ticker, uri, decimals))
    conn.commit()
    conn.close()
    