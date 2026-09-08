import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import sqlite3
import json
import bcrypt
import datetime
import random
import os
from typing import List, Dict
from faker import Faker
from scripts.logger import get_logger
from scripts.config import DB_PATH

logger = get_logger(__name__)
fake = Faker()

def create_tables(cursor: sqlite3.Cursor) -> None:
    """Create required tables if they don't exist."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            price REAL NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            items TEXT NOT NULL,
            total_price REAL NOT NULL,
            status TEXT NOT NULL,
            date TEXT DEFAULT (DATE('now')),
            time TEXT DEFAULT (TIME('now'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL
        )
    """)
    logger.info("Tables created or already exist.")

def create_database(db_path=DB_PATH) -> None:
    try:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            logger.info({"db_path": str(db_path), "message": "Connected to SQLite database"})
            create_tables(cursor)
            populate_menu(cursor)
            populate_orders(cursor, use_defaults=False)
            populate_users(cursor)

            conn.commit()
            logger.info({"message": "Database populated successfully"})

        print("✅ Database populated successfully!")
    except Exception as e:
        logger.error({"error": str(e), "message": "Failed to create/populate database"})
        raise

def populate_menu(cursor: sqlite3.Cursor) -> None:
    """🍽️ Populate the menu table with items and prices."""
    menu_items = [
        ("cheese burger", 5.99), ("chicken burger", 6.99), ("veggie burger", 5.49),
        ("pepperoni pizza", 12.99), ("margherita pizza", 11.49), ("bbq chicken pizza", 13.99),
        ("grilled chicken sandwich", 7.99), ("club sandwich", 6.99), ("spaghetti carbonara", 9.99),
        ("fettuccine alfredo", 10.49), ("tandoori chicken", 11.99), ("butter chicken", 12.49),
        ("beef steak", 15.99), ("chicken biryani", 8.99), ("mutton biryani", 10.99),
        ("prawn curry", 13.49), ("fish and chips", 9.49), ("french fries", 3.99),
        ("garlic bread", 4.49), ("chocolate brownie", 5.49), ("vanilla ice cream", 3.99),
        ("strawberry shake", 4.99), ("mango smoothie", 5.49), ("coca-cola", 2.49),
        ("pepsi", 2.49), ("fresh orange juice", 4.99)
    ]
    try:
        cursor.executemany(
            "INSERT OR IGNORE INTO menu (name, price) VALUES (?, ?)",
            menu_items
        )
        logger.info({"count": len(menu_items), "message": "Menu items inserted"})
    except sqlite3.Error as e:
        logger.error({"error": str(e), "message": "Failed to populate menu"})
        raise

def populate_orders(cursor: sqlite3.Cursor, use_defaults: bool = False) -> None:
    cursor.execute("SELECT name, price FROM menu")
    menu_dict = {row[0]: row[1] for row in cursor.fetchall()}
    
    statuses = ["Pending", "Preparing", "In Process", "Ready", "Completed", "Delivered", "Canceled"]
    status_weights = [0.1, 0.1, 0.1, 0.1, 0.2, 0.4, 0.1] 
    
    orders = []
    for _ in range(150):
        num_items = random.randint(1, 5)
        order_items = random.sample(list(menu_dict.keys()), num_items)
        order_dict = {item: random.randint(1, 3) for item in order_items}
        total_price = sum(menu_dict[item] * qty for item, qty in order_dict.items())
        status = random.choices(statuses, weights=status_weights, k=1)[0]
        
        if use_defaults:
            orders.append((json.dumps(order_dict), total_price, status))
        else:
            order_date = fake.date_between(start_date=datetime.date(2023, 1, 1), end_date=datetime.date(2025, 7, 7))
            order_time = fake.time_object().replace(hour=random.randint(8, 23), minute=random.randint(0, 59), second=random.randint(0, 59))
            order_time_str = order_time.strftime("%I:%M:%S %p")
            orders.append((
                json.dumps(order_dict),
                total_price,
                status,
                order_date.strftime("%Y-%m-%d"),
                order_time_str
            ))
    
    try:
        if use_defaults:
            cursor.executemany(
                "INSERT INTO orders (items, total_price, status) VALUES (?, ?, ?)",
                orders
            )
        else:
            cursor.executemany(
                "INSERT INTO orders (items, total_price, status, date, time) VALUES (?, ?, ?, ?, ?)",
                orders
            )
        logger.info({"count": len(orders), "use_defaults": use_defaults, "message": "Orders inserted"})
    except sqlite3.Error as e:
        logger.error({"error": str(e), "message": "Failed to populate orders"})
        raise

def populate_users(cursor: sqlite3.Cursor) -> None:
    """👤 Populate staff and customers tables with sample users."""
    # Staff
    staff = [
        ("admin", bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), "admin"),
        ("chef", bcrypt.hashpw("chef123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), "kitchen_staff"),
        ("support", bcrypt.hashpw("support123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), "customer_support"),
    ]
    
    # Customers
    customers = [
        (f"user{i}", bcrypt.hashpw(f"pass{i}".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), f"user{i}@example.com")
        for i in range(1, 11)
    ]
    
    try:
        cursor.executemany(
            "INSERT OR IGNORE INTO staff (username, password_hash, role) VALUES (?, ?, ?)",
            staff
        )
        cursor.executemany(
            "INSERT OR IGNORE INTO customers (username, password_hash, email) VALUES (?, ?, ?)",
            customers
        )
        logger.info({"staff_count": len(staff), "customer_count": len(customers), "message": "Users inserted"})
    except sqlite3.Error as e:
        logger.error({"error": str(e), "message": "Failed to populate users"})
        raise

if __name__ == "__main__":
    create_database()