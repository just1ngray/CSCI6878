import sqlite3
from functools import cache

@cache
def db() -> sqlite3.Cursor:
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()

    cursor.executescript("""
        BEGIN;
        CREATE TABLE IF NOT EXISTS repos (
            rank    INTEGER PRIMARY KEY,
            owner   TEXT    NOT NULL,
            project TEXT    NOT NULL,
            stars   INTEGER,
            visited BOOLEAN DEFAULT "False"
        );
        CREATE TABLE IF NOT EXISTS repo_langs (
            repo    INTEGER NOT NULL,
            lang    TEXT    NOT NULL,
            weight  INTEGER NOT NULL,
            PRIMARY KEY (repo, lang),
            FOREIGN KEY (repo) REFERENCES repos (rank)
        );
        CREATE TABLE IF NOT EXISTS users (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS contributors (
            repo    INTEGER NOT NULL,
            user    INTEGER NOT NULL,
            commits INTEGER NOT NULL,
            PRIMARY KEY (repo, user),
            FOREIGN KEY (repo) REFERENCES repos (rank),
            FOREIGN KEY (user) REFERENCES users (id)
        );
        COMMIT;
    """)

    return cursor
