import datetime, json, bcrypt, pandas as pd, aiomysql
from typing import Dict, Optional, List
from scripts.logger import get_logger
from scripts.config import (
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DATABASE,
)

logger = get_logger(__name__)


class AsyncDatabase:
    """Async MySQL database handler for DineMate.

    Usage:
        async with AsyncDatabase() as db:
            menu = await db.load_menu()
    """

    def __init__(
        self,
        host: str = MYSQL_HOST,
        port: int = MYSQL_PORT,
        user: str = MYSQL_USER,
        password: str = MYSQL_PASSWORD,
        db: str = MYSQL_DATABASE,
    ):
        """🗄️ Initialize AsyncDatabase with MySQL connection parameters."""
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.db = db
        self.connection = None
        self.cursor = None

    async def __aenter__(self):
        """Open the async database connection and return self."""
        self.connection = await aiomysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            db=self.db,
            cursorclass=aiomysql.DictCursor,
            autocommit=False,
        )
        self.cursor = await self.connection.cursor()
        logger.info("✅ Connected to MySQL database")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close the cursor and connection on exit."""
        if self.cursor:
            await self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("🔐 Database connection closed")

    async def fetch_order_data(self, status: Optional[str] = "Delivered") -> pd.DataFrame:
        """📊 Fetch orders as a Pandas DataFrame filtered by status.

        Args:
            status (Optional[str]): Order status filter, or 'All' for everything.

        Returns:
            pd.DataFrame: Order data, or an empty DataFrame on error.
        """
        logger.info("📊 Fetching order data for analytics")
        query = "SELECT id, items, total_price, status, date, time FROM orders"
        try:
            if status and status != "All":
                query += " WHERE status = %s"
                await self.cursor.execute(query, (status,))
            else:
                await self.cursor.execute(query)

            rows = await self.cursor.fetchall()
            data = [dict(row) for row in rows]
            return pd.DataFrame(data)
        except Exception as e:
            logger.error({"error": str(e), "message": "❌ Error fetching order data"})
            return pd.DataFrame()

    async def load_menu(self) -> Optional[Dict[str, float]]:
        """🍽️ Load menu items as a dictionary mapping item names to prices.

        Returns:
            Optional[Dict[str, float]]: Menu dict or None if empty / error.
        """
        try:
            await self.cursor.execute("SELECT name, price FROM menu")
            rows = await self.cursor.fetchall()
            menu = {row["name"]: float(row["price"]) for row in rows}
            logger.info("🍔 Fetched menu items")
            return menu if menu else None
        except Exception as e:
            logger.error({"error": str(e), "message": "❌ Error fetching menu"})
            return None

    async def get_max_id(self) -> int:
        """🔢 Get next available order ID.

        Returns:
            int: Next order ID.
        """
        try:
            await self.cursor.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM orders")
            result = await self.cursor.fetchone()
            current_max = result["max_id"] if result else 0
            return current_max + 1
        except Exception as e:
            logger.error({"error": str(e), "message": "❌ Error fetching max ID"})
            return 1

    async def store_order_db(
        self,
        order_dict: Dict[str, int],
        price: float,
        status: str = "Pending",
        username: Optional[str] = None,
        payment_status: str = "Unpaid",
        razorpay_order_id: Optional[str] = None,
        payment_link: Optional[str] = None
    ) -> Optional[int]:
        """📝 Store a new order in the database with payment tracking."""
        try:
            now = datetime.datetime.now()
            order_id = await self.get_max_id()
            await self.cursor.execute(
                """
                INSERT INTO orders (id, items, total_price, status, date, time, username, payment_status, razorpay_order_id, payment_link)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (order_id, json.dumps(order_dict), price, status, now.strftime("%Y-%m-%d"), now.strftime("%I:%M:%S %p"), username, payment_status, razorpay_order_id, payment_link)
            )
            await self.connection.commit()
            logger.info(f"✅ Order stored with ID #{order_id}")
            return order_id
        except Exception as e:
            logger.error({"error": str(e), "message": "❌ Error storing order"})
            return None

    async def update_order_payment(
        self,
        order_id: int,
        payment_status: str,
        razorpay_payment_id: Optional[str] = None,
        razorpay_order_id: Optional[str] = None,
        payment_link: Optional[str] = None
    ) -> bool:
        """💳 Update payment information for an order."""
        try:
            updates = ["payment_status = %s"]
            params = [payment_status]
            if razorpay_payment_id:
                updates.append("razorpay_payment_id = %s")
                params.append(razorpay_payment_id)
            if razorpay_order_id:
                updates.append("razorpay_order_id = %s")
                params.append(razorpay_order_id)
            if payment_link:
                updates.append("payment_link = %s")
                params.append(payment_link)

            params.append(order_id)
            query = f"UPDATE orders SET {', '.join(updates)} WHERE id = %s"
            await self.cursor.execute(query, tuple(params))
            await self.connection.commit()
            logger.info(f"💳 Payment status for order #{order_id} updated to '{payment_status}'")
            return True
        except Exception as e:
            logger.error({"error": str(e), "message": "❌ Error updating order payment"})
            return False

    async def get_last_user_order(self, username: Optional[str] = None) -> Optional[Dict]:
        """📦 Fetch the user's most recent non-canceled order.

        Args:
            username (Optional[str]): Filter by username. If None, returns the latest order globally.

        Returns:
            Optional[Dict]: Order dict, or None if not found.
        """
        try:
            if username:
                await self.cursor.execute(
                    """
                    SELECT id, items, total_price, status, date, time, username
                    FROM orders
                    WHERE username = %s AND status != 'Canceled'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (username,)
                )
            else:
                await self.cursor.execute(
                    """
                    SELECT id, items, total_price, status, date, time, username
                    FROM orders
                    WHERE status != 'Canceled'
                    ORDER BY id DESC
                    LIMIT 1
                    """
                )
            row = await self.cursor.fetchone()
            if row:
                order = dict(row)
                if isinstance(order.get("items"), str):
                    order["items"] = json.loads(order["items"])
                return order
            return None
        except Exception as e:
            logger.error({"error": str(e), "message": "❌ Error fetching last user order"})
            return None

    async def check_order_status_db(self, order_id: int) -> str:
        """🔍 Check order status and estimated delivery time.

        Args:
            order_id (int): Order ID.

        Returns:
            str: Human-readable status message.
        """
        logger.info("📦 Checking order status")
        try:
            await self.cursor.execute("SELECT status, time, date FROM orders WHERE id = %s", (order_id,))
            row = await self.cursor.fetchone()
            if not row:
                return f"No order found with ID {order_id}"

            status = row["status"]
            if status in {"Canceled", "Delivered"}:
                return f"Order {order_id} is {status.lower()}."

            date_str = str(row["date"])
            time_str = str(row["time"])
            # Support both '%I:%M:%S %p' and '%H:%M:%S' formats
            try:
                order_time = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M:%S %p")
            except ValueError:
                order_time = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")

            estimated_time = order_time + datetime.timedelta(minutes=40)
            now = datetime.datetime.now()

            if now > estimated_time:
                delay = int((now - estimated_time).total_seconds() / 60)
                return f"Status: {status}, Delivery: {estimated_time.strftime('%I:%M %p')} (delayed ~{delay} min)"
            return f"Status: {status}, Delivery: {estimated_time.strftime('%I:%M %p')}"
        except Exception as e:
            logger.error({"error": str(e), "message": "❌ Error fetching status"})
            return f"Error: {e}"

    async def cancel_order_after_confirmation(self, order_id: int) -> str:
        """❌ Cancel an order if it was placed within the last 10 minutes.

        Args:
            order_id (int): Order ID.

        Returns:
            str: Result message.
        """
        logger.info("🚫 Checking cancellation")
        try:
            await self.cursor.execute("SELECT status, date, time FROM orders WHERE id = %s", (order_id,))
            row = await self.cursor.fetchone()
            if not row:
                return f"No order found with ID {order_id}"

            if row["status"] in {"Canceled", "Completed", "Delivered"}:
                return f"Order {order_id} is {row['status'].lower()}."

            date_str = str(row["date"])
            time_str = str(row["time"])
            try:
                order_time = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M:%S %p")
            except ValueError:
                order_time = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")

            if (datetime.datetime.now() - order_time).total_seconds() > 600:
                return "Cannot cancel: past 10-min window."

            await self.cursor.execute("UPDATE orders SET status = %s WHERE id = %s", ("Canceled", order_id))
            await self.connection.commit()
            return f"Order {order_id} canceled."
        except Exception as e:
            logger.error({"error": str(e), "message": "❌ Error canceling"})
            return f"Error: {e}"

    async def modify_order_after_confirmation(self, order_id: int, updated_items: str, new_total_price: float) -> str:
        """✏️ Modify an order's items and price if within 10 minutes of placement.

        Args:
            order_id (int): Order ID.
            updated_items (str): JSON string of items and quantities.
            new_total_price (float): Recalculated total price.

        Returns:
            str: Status message.
        """
        logger.info("✍️ Checking modification")
        try:
            items = json.loads(updated_items) if isinstance(updated_items, str) else updated_items
            if not items:
                return "⚠️ No items provided."

            menu = await self.load_menu() or {}
            valid_items = {item.lower() for item in menu}
            for item in items:
                if item.lower() not in valid_items:
                    return f"⚠️ '{item}' not in menu."

            await self.cursor.execute("SELECT status, date, time FROM orders WHERE id = %s", (order_id,))
            row = await self.cursor.fetchone()
            if not row:
                return f"⚠️ No order found with ID {order_id}."

            if row["status"] not in {"Pending", "Preparing"}:
                return f"⚠️ Order {order_id} is {row['status'].lower()}."

            date_str = str(row["date"])
            time_str = str(row["time"])
            try:
                order_time = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M:%S %p")
            except ValueError:
                order_time = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")

            if (datetime.datetime.now() - order_time).total_seconds() > 600:
                return "⚠️ Cannot modify: past 10-min window."

            await self.cursor.execute(
                "UPDATE orders SET items = %s, total_price = %s WHERE id = %s",
                (json.dumps(items), new_total_price, order_id)
            )
            await self.connection.commit()

            summary = ", ".join(f"{item}: {qty}" for item, qty in items.items())
            return f"✅ Order {order_id} updated successfully. Items: {summary}, Total: ₹{new_total_price:.2f}"
        except (ValueError, TypeError) as e:
            logger.error({"error": str(e), "message": "❌ Failed to update"})
            return f"⚠️ Error: {str(e)}"

    async def get_order_by_id(self, order_id: int) -> Dict[str, any]:
        """🔍 Get full order details including modification window info.

        Args:
            order_id (int): Order ID.

        Returns:
            Dict[str, any]: Order dict with a 'message' key, or error dict.
        """
        logger.info("🔎 Fetching order details")
        try:
            await self.cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
            row = await self.cursor.fetchone()
            if not row:
                return {"status": "error", "message": f"No order found with ID {order_id}"}

            order = dict(row)
            items = json.loads(order["items"]) if isinstance(order["items"], str) else order["items"]
            msg = f"Order {order_id}: {', '.join(f'{k}: {v}' for k,v in items.items())}, Total: ₹{order['total_price']:.2f}, Status: {order['status']}"

            if order["status"] == "Pending":
                date_str = str(order["date"])
                time_str = str(order["time"])
                try:
                    placed = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M:%S %p")
                except ValueError:
                    placed = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                minutes = (datetime.datetime.now() - placed).total_seconds() / 60
                msg += f"\n{int(10 - minutes)} min to modify" if minutes <= 10 else "\nCannot modify: past 10-min window."
            else:
                msg += f"\nCannot modify: order is {order['status'].lower()}."

            order.update({"items": items, "message": msg})
            return order
        except Exception as e:
            logger.error({"error": str(e), "message": "❌ Error fetching order"})
            return {"status": "error", "message": f"Error: {e}"}

    async def add_user(self, username: str, password: str, email: str, role: str = "customer") -> str:
        """👤 Register a new user (customer or staff).

        Args:
            username (str): Alphanumeric username.
            password (str): Plain-text password (will be hashed with bcrypt).
            email (str): User email address.
            role (str): One of 'customer', 'admin', 'kitchen_staff', 'customer_support'.

        Returns:
            str: Result message.
        """
        try:
            if not (username.isalnum() and "@" in email and "." in email):
                return "Invalid username or email."

            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

            if role in {"admin", "kitchen_staff", "customer_support"}:
                await self.cursor.execute("INSERT INTO staff (username, password_hash, role) VALUES (%s, %s, %s)", (username, password_hash, role))
            else:
                await self.cursor.execute("INSERT INTO customers (username, password_hash, email) VALUES (%s, %s, %s)", (username, password_hash, email))

            await self.connection.commit()
            return f"User {username} added."
        except Exception as e:
            logger.error({"error": str(e), "message": "❌ Error adding user"})
            return f"Error: {e}"

    async def verify_user(self, username: str, password: str) -> Optional[str]:
        """🔐 Verify user credentials and return their role.

        Checks the staff table first, then the customers table.

        Args:
            username (str): Username.
            password (str): Plain-text password.

        Returns:
            Optional[str]: User role ('admin', 'kitchen_staff', 'customer_support', 'customer'),
                           or None if credentials are invalid.
        """
        try:
            if not username.isalnum():
                return None

            # Check staff table first.
            await self.cursor.execute("SELECT password_hash, role FROM staff WHERE username = %s", (username,))
            row = await self.cursor.fetchone()
            if row and bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
                return row["role"]

            # Fall back to customers table.
            await self.cursor.execute("SELECT password_hash FROM customers WHERE username = %s", (username,))
            row = await self.cursor.fetchone()
            if row and bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
                return "customer"

            return None
        except Exception as e:
            logger.error({"error": str(e), "message": "❌ Error verifying user"})
            return None

    async def check_existing_user(self, username: str, email: str) -> Optional[Dict]:
        """✅ Check if a username or email is already registered.

        Args:
            username (str): Username to check.
            email (str): Email to check.

        Returns:
            Optional[Dict]: The existing user row, or None if not found.
        """
        try:
            await self.cursor.execute("SELECT * FROM customers WHERE username = %s OR email = %s", (username, email))
            row = await self.cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error({"error": str(e), "message": "❌ Error checking existing user"})
            return None

    async def create_escalation(
        self,
        username: str,
        customer_issue: str,
        conversation_summary: str,
        target_phone: str = "+917906773761",
        customer_phone: Optional[str] = None,
        order_id: Optional[int] = None,
        status: str = "Pending",
        twilio_call_sid: Optional[str] = None,
        twilio_sms_sid: Optional[str] = None,
    ) -> Optional[int]:
        """🚨 Insert a warm transfer escalation ticket."""
        try:
            query = """
                INSERT INTO escalations 
                (username, customer_phone, target_phone, order_id, customer_issue, conversation_summary, status, twilio_call_sid, twilio_sms_sid)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            await self.cursor.execute(
                query,
                (username, customer_phone, target_phone, order_id, customer_issue, conversation_summary, status, twilio_call_sid, twilio_sms_sid)
            )
            await self.connection.commit()
            escalation_id = self.cursor.lastrowid
            logger.info(f"🚨 Warm transfer escalation ticket #{escalation_id} recorded for user '{username}'")
            return escalation_id
        except Exception as e:
            logger.error({"error": str(e), "message": "❌ Failed to record escalation ticket"})
            return None

    async def fetch_escalations(self, status: Optional[str] = None) -> List[Dict]:
        """🚨 Fetch escalation records asynchronously."""
        try:
            query = "SELECT * FROM escalations"
            params = []
            if status and status != "All":
                query += " WHERE status = %s"
                params.append(status)
            query += " ORDER BY created_at DESC"
            await self.cursor.execute(query, tuple(params))
            rows = await self.cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error({"error": str(e), "message": "❌ Failed to fetch escalations"})
            return []


class Database:
    """Synchronous MySQL database handler for DineMate UI, auth, orders, and menu management."""

    def __init__(
        self,
        host: str = MYSQL_HOST,
        port: int = MYSQL_PORT,
        user: str = MYSQL_USER,
        password: str = MYSQL_PASSWORD,
        db: str = MYSQL_DATABASE,
    ):
        import pymysql
        import pymysql.cursors
        self.connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=db,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )
        self.cursor = self.connection.cursor()

    # --- Menu Operations ---
    def load_menu(self) -> Dict[str, float]:
        """Loads menu dictionary {name: price}."""
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT name, price FROM menu ORDER BY name")
            rows = cursor.fetchall()
            return {r["name"]: float(r["price"]) for r in rows}

    def get_menu_items(self) -> List[Dict]:
        """Returns list of all menu items."""
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT id, name, price FROM menu ORDER BY name")
            return [{"id": r["id"], "name": r["name"], "price": float(r["price"])} for r in cursor.fetchall()]

    def check_item_exists(self, item_name: str) -> bool:
        """Checks if a menu item exists."""
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM menu WHERE LOWER(name) = LOWER(%s)", (item_name.strip(),))
            return cursor.fetchone() is not None

    def add_new_item(self, item_name: str, price: float) -> bool:
        """Adds a new menu item."""
        if self.check_item_exists(item_name) or price <= 0:
            return False
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("INSERT INTO menu (name, price) VALUES (%s, %s)", (item_name.strip(), price))
            return True
        except Exception as e:
            logger.error(f"Error adding menu item {item_name}: {e}")
            return False

    def remove_item(self, item_name: str) -> bool:
        """Deletes a menu item."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("DELETE FROM menu WHERE LOWER(name) = LOWER(%s)", (item_name.strip(),))
            return True
        except Exception as e:
            logger.error(f"Error removing menu item {item_name}: {e}")
            return False

    def update_item_price(self, item_name: str, new_price: float) -> bool:
        """Updates the price of a menu item."""
        if new_price <= 0:
            return False
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("UPDATE menu SET price = %s WHERE LOWER(name) = LOWER(%s)", (new_price, item_name.strip()))
            return True
        except Exception as e:
            logger.error(f"Error updating price for {item_name}: {e}")
            return False

    # --- User Authentication ---
    def verify_user(self, username: str, password: str) -> Optional[str]:
        """Verifies user credentials across staff and customer tables."""
        if not username:
            return None
        with self.connection.cursor() as cursor:
            # Check staff first
            cursor.execute("SELECT password_hash, role FROM staff WHERE username = %s", (username.strip(),))
            row = cursor.fetchone()
            if row and bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
                return row["role"]

            # Fall back to customers
            cursor.execute("SELECT password_hash FROM customers WHERE username = %s", (username.strip(),))
            row = cursor.fetchone()
            if row and bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
                return "customer"

        return None

    def check_existing_user(self, username: str, email: str) -> bool:
        """Checks if a username or email is already registered."""
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM customers WHERE username = %s OR email = %s", (username.strip(), email.strip()))
            if cursor.fetchone():
                return True
            cursor.execute("SELECT 1 FROM staff WHERE username = %s", (username.strip(),))
            return cursor.fetchone() is not None

    def add_user(self, username: str, password: str, email: str, role: str = "customer") -> bool:
        """Registers a new user."""
        try:
            if not (username and password and email):
                return False
            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            with self.connection.cursor() as cursor:
                if role in {"admin", "kitchen_staff", "customer_support"}:
                    cursor.execute("INSERT INTO staff (username, password_hash, role) VALUES (%s, %s, %s)",
                                   (username.strip(), password_hash, role))
                else:
                    cursor.execute("INSERT INTO customers (username, password_hash, email) VALUES (%s, %s, %s)",
                                   (username.strip(), password_hash, email.strip()))
            return True
        except Exception as e:
            logger.error(f"Error registering user {username}: {e}")
            return False

    # --- Order Management ---
    def get_all_orders(self, status: Optional[str] = None) -> List[Dict]:
        """Retrieves orders list."""
        with self.connection.cursor() as cursor:
            if status and status != "All":
                cursor.execute(
                    "SELECT id, items, total_price, status, time, date, username FROM orders WHERE status = %s ORDER BY id DESC",
                    (status,)
                )
            else:
                cursor.execute(
                    "SELECT id, items, total_price, status, time, date, username FROM orders ORDER BY id DESC"
                )
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "items": r["items"] if isinstance(r["items"], str) else json.dumps(r["items"]),
                    "total_price": float(r["total_price"]),
                    "status": r["status"],
                    "time": r.get("time", ""),
                    "date": r.get("date", ""),
                    "username": r.get("username", "")
                }
                for r in rows
            ]

    def fetch_order_data(self, status: Optional[str] = "All") -> pd.DataFrame:
        """Fetches orders as a DataFrame for analytics."""
        orders = self.get_all_orders(status=status)
        if not orders:
            return pd.DataFrame()
        df = pd.DataFrame(orders)
        df["total_price"] = pd.to_numeric(df["total_price"], errors="coerce").fillna(0.0)
        return df

    def get_order_details(self, order_id: int) -> Optional[Dict]:
        """Fetches details for a single order."""
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT id, items, total_price, status, time, date, username FROM orders WHERE id = %s", (order_id,))
            r = cursor.fetchone()
            if not r:
                return None
            return {
                "id": r["id"],
                "items": r["items"] if isinstance(r["items"], str) else json.dumps(r["items"]),
                "total_price": float(r["total_price"]),
                "status": r["status"],
                "time": r.get("time", ""),
                "date": r.get("date", ""),
                "username": r.get("username", "")
            }

    def update_order_status(self, order_id: int, new_status: str) -> bool:
        """Updates the status of an order."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("UPDATE orders SET status = %s WHERE id = %s", (new_status, order_id))
            return True
        except Exception as e:
            logger.error(f"Error updating order status for #{order_id}: {e}")
            return False

    def modify_order_after_confirmation(self, order_id: int, valid_items: dict, total_price: float) -> str:
        """Modifies order items if within 10 minutes."""
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT date, time, status FROM orders WHERE id = %s", (order_id,))
            order = cursor.fetchone()
            if not order:
                return "Order not found."
            if order["status"] == "Cancelled":
                return "Order is already cancelled."

            time_str = f"{order.get('date', '')} {order.get('time', '')}".strip()
            created_at = None
            for fmt in ("%Y-%m-%d %I:%M:%S %p", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    created_at = datetime.datetime.strptime(time_str, fmt)
                    break
                except ValueError:
                    pass

            if created_at:
                elapsed = (datetime.datetime.now() - created_at).total_seconds() / 60
                if elapsed > 10:
                    return f"Cannot modify order: {elapsed:.1f} minutes elapsed (10-minute limit)."

            cursor.execute(
                "UPDATE orders SET items = %s, total_price = %s WHERE id = %s",
                (json.dumps(valid_items), total_price, order_id)
            )
            return f"Order #{order_id} updated successfully!"

    def cancel_order_after_confirmation(self, order_id: int) -> str:
        """Cancels an order if within 10 minutes."""
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT date, time, status FROM orders WHERE id = %s", (order_id,))
            order = cursor.fetchone()
            if not order:
                return "Order not found."
            if order["status"] == "Cancelled":
                return "Order is already cancelled."

            time_str = f"{order.get('date', '')} {order.get('time', '')}".strip()
            created_at = None
            for fmt in ("%Y-%m-%d %I:%M:%S %p", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    created_at = datetime.datetime.strptime(time_str, fmt)
                    break
                except ValueError:
                    pass

            if created_at:
                elapsed = (datetime.datetime.now() - created_at).total_seconds() / 60
                if elapsed > 10:
                    return f"Cannot cancel order: {elapsed:.1f} minutes elapsed (10-minute limit)."

            cursor.execute("UPDATE orders SET status = 'Cancelled' WHERE id = %s", (order_id,))
            return f"Order #{order_id} cancelled successfully!"

    def store_order_db(
        self,
        items: dict,
        total_price: float,
        username: Optional[str] = None,
        payment_status: str = "Unpaid",
        razorpay_order_id: Optional[str] = None,
        payment_link: Optional[str] = None
    ) -> Optional[int]:
        """Stores a newly placed order with payment tracking."""
        try:
            now = datetime.datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%I:%M:%S %p")
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO orders (items, total_price, status, date, time, username, payment_status, razorpay_order_id, payment_link)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (json.dumps(items), total_price, "Pending", date_str, time_str, username, payment_status, razorpay_order_id, payment_link)
                )
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error storing order: {e}")
            return None

    def update_order_payment(
        self,
        order_id: int,
        payment_status: str,
        razorpay_payment_id: Optional[str] = None,
        razorpay_order_id: Optional[str] = None,
        payment_link: Optional[str] = None
    ) -> bool:
        """💳 Update payment information for an order synchronously."""
        try:
            updates = ["payment_status = %s"]
            params = [payment_status]
            if razorpay_payment_id:
                updates.append("razorpay_payment_id = %s")
                params.append(razorpay_payment_id)
            if razorpay_order_id:
                updates.append("razorpay_order_id = %s")
                params.append(razorpay_order_id)
            if payment_link:
                updates.append("payment_link = %s")
                params.append(payment_link)

            params.append(order_id)
            query = f"UPDATE orders SET {', '.join(updates)} WHERE id = %s"
            with self.connection.cursor() as cursor:
                cursor.execute(query, tuple(params))
                self.connection.commit()
            logger.info(f"💳 Payment status for order #{order_id} updated to '{payment_status}'")
            return True
        except Exception as e:
            logger.error(f"Error updating order payment: {e}")
            return False

    def create_escalation(
        self,
        username: str,
        customer_issue: str,
        conversation_summary: str,
        target_phone: str = "+917906773761",
        customer_phone: Optional[str] = None,
        order_id: Optional[int] = None,
        status: str = "Pending",
        twilio_call_sid: Optional[str] = None,
        twilio_sms_sid: Optional[str] = None,
    ) -> Optional[int]:
        """🚨 Insert a warm transfer escalation ticket synchronously."""
        try:
            with self.connection.cursor() as cursor:
                query = """
                    INSERT INTO escalations 
                    (username, customer_phone, target_phone, order_id, customer_issue, conversation_summary, status, twilio_call_sid, twilio_sms_sid)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(
                    query,
                    (username, customer_phone, target_phone, order_id, customer_issue, conversation_summary, status, twilio_call_sid, twilio_sms_sid)
                )
                self.connection.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error creating escalation: {e}")
            return None

    def fetch_escalations(self, status: Optional[str] = None) -> List[Dict]:
        """🚨 Fetch escalation records synchronously for Streamlit dashboard."""
        try:
            with self.connection.cursor() as cursor:
                query = "SELECT * FROM escalations"
                params = []
                if status and status != "All":
                    query += " WHERE status = %s"
                    params.append(status)
                query += " ORDER BY created_at DESC"
                cursor.execute(query, tuple(params))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error fetching escalations: {e}")
            return []

    def update_escalation_status(self, escalation_id: int, new_status: str) -> bool:
        """🚨 Update an escalation ticket status."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE escalations SET status = %s WHERE id = %s",
                    (new_status, escalation_id)
                )
                self.connection.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating escalation #{escalation_id}: {e}")
            return False

    def close_connection(self):
        if hasattr(self, "cursor") and self.cursor:
            try:
                self.cursor.close()
            except Exception:
                pass
        if hasattr(self, "connection") and self.connection and self.connection.open:
            try:
                self.connection.close()
            except Exception:
                pass