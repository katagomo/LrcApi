from mod.auth import webui
from mod.auth.authentication import require_auth
from mod.lrc import standard
from . import *

import sqlite3
import os

from threading import Lock

db_source = os.path.join(os.getcwd(), 'data', 'userdata.db')
conn = sqlite3.connect(db_source, check_same_thread=False)
lock: Lock = Lock()


# SQL数据库操作
class SQL_DB:
    @staticmethod
    def create_table(table_name: str, table_columns: dict):
        with lock:
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({table_columns})")
            conn.commit()

    @staticmethod
    def insert(table_name: str, table_columns: dict):
        with lock:
            conn.execute(f"INSERT INTO {table_name} ({table_columns}) VALUES ({table_columns})")
            conn.commit()

    @staticmethod
    def update(table_name: str, table_columns: dict):
        with lock:
            conn.execute(f"UPDATE {table_name} SET {table_columns}")
            conn.commit()

    @staticmethod
    def delete(table_name: str, table_columns: dict):
        with lock:
            conn.execute(f"DELETE FROM {table_name} WHERE {table_columns}")
            conn.commit()
