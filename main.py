from fastmcp import FastMCP
import os
import aiosqlite
import tempfile

# Use temporary directory which should be writable
TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

print(f"Database path: {DB_PATH}")

mcp = FastMCP("ExpenseTracker")

def init_db():
    """Initialize database synchronously at module load"""
    try:
        import sqlite3
        with sqlite3.connect(DB_PATH) as c:
            c.execute("PRAGMA journal_mode=WAL")
            
            # Create expenses table
            c.execute("""
                CREATE TABLE IF NOT EXISTS expenses(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT DEFAULT '',
                    note TEXT DEFAULT ''
                )
            """)
            
            # Create income table
            c.execute("""
                CREATE TABLE IF NOT EXISTS income(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    source TEXT NOT NULL,
                    note TEXT DEFAULT ''
                )
            """)
            
            # Test write access
            c.execute("INSERT OR IGNORE INTO expenses(date, amount, category) VALUES ('2000-01-01', 0, 'test')")
            c.execute("DELETE FROM expenses WHERE category = 'test'")
            print("Database initialized successfully with write access")
    except Exception as e:
        print(f"Database initialization error: {e}")
        raise

# Initialize database
init_db()

# ============= EXPENSE FUNCTIONS =============

@mcp.tool()
async def add_expense(date, amount, category, subcategory="", note=""):
    """Add a new expense entry to the database."""
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                "INSERT INTO expenses(date, amount, category, subcategory, note) VALUES (?,?,?,?,?)",
                (date, amount, category, subcategory, note)
            )
            expense_id = cur.lastrowid
            await c.commit()
            return {"status": "ok", "id": expense_id}
    except Exception as e:
        if "readonly" in str(e).lower():
            return {"status": "error", "message": "Database is in read-only mode. Check file permissions."}
        return {"status": "error", "message": f"Database error: {str(e)}"}

@mcp.tool()
async def edit_expense(expense_id, date=None, amount=None, category=None, subcategory=None, note=None):
    """Edit an existing expense entry. Only provided fields will be updated."""
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            # Check if expense exists
            cur = await c.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
            if not await cur.fetchone():
                return {"status": "error", "message": f"Expense with id {expense_id} not found"}
            
            # Build dynamic update query
            updates = []
            params = []
            
            if date is not None:
                updates.append("date = ?")
                params.append(date)
            if amount is not None:
                updates.append("amount = ?")
                params.append(amount)
            if category is not None:
                updates.append("category = ?")
                params.append(category)
            if subcategory is not None:
                updates.append("subcategory = ?")
                params.append(subcategory)
            if note is not None:
                updates.append("note = ?")
                params.append(note)
            
            if not updates:
                return {"status": "error", "message": "No fields to update"}
            
            params.append(expense_id)
            query = f"UPDATE expenses SET {', '.join(updates)} WHERE id = ?"
            await c.execute(query, params)
            await c.commit()
            
            return {"status": "ok", "id": expense_id, "updated_fields": len(updates)}
    except Exception as e:
        return {"status": "error", "message": f"Error editing expense: {str(e)}"}

@mcp.tool()
async def delete_expense(expense_id):
    """Delete an expense entry by ID."""
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            # Check if expense exists
            cur = await c.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
            if not await cur.fetchone():
                return {"status": "error", "message": f"Expense with id {expense_id} not found"}
            
            await c.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
            await c.commit()
            return {"status": "ok", "id": expense_id, "message": "Expense deleted successfully"}
    except Exception as e:
        return {"status": "error", "message": f"Error deleting expense: {str(e)}"}

@mcp.tool()
async def list_expenses(start_date, end_date):
    """List expense entries within an inclusive date range."""
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                """
                SELECT id, date, amount, category, subcategory, note
                FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC, id DESC
                """,
                (start_date, end_date)
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in await cur.fetchall()]
    except Exception as e:
        return {"status": "error", "message": f"Error listing expenses: {str(e)}"}

# ============= INCOME FUNCTIONS =============

@mcp.tool()
async def add_income(date, amount, source, note=""):
    """Add income/credit entry (e.g., salary, bonus, refund)."""
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                "INSERT INTO income(date, amount, source, note) VALUES (?,?,?,?)",
                (date, amount, source, note)
            )
            income_id = cur.lastrowid
            await c.commit()
            return {"status": "ok", "id": income_id}
    except Exception as e:
        if "readonly" in str(e).lower():
            return {"status": "error", "message": "Database is in read-only mode. Check file permissions."}
        return {"status": "error", "message": f"Database error: {str(e)}"}

@mcp.tool()
async def list_income(start_date, end_date):
    """List income entries within an inclusive date range."""
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                """
                SELECT id, date, amount, source, note
                FROM income
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC, id DESC
                """,
                (start_date, end_date)
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in await cur.fetchall()]
    except Exception as e:
        return {"status": "error", "message": f"Error listing income: {str(e)}"}

@mcp.tool()
async def edit_income(income_id, date=None, amount=None, source=None, note=None):
    """Edit an existing income entry. Only provided fields will be updated."""
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            # Check if income exists
            cur = await c.execute("SELECT * FROM income WHERE id = ?", (income_id,))
            if not await cur.fetchone():
                return {"status": "error", "message": f"Income with id {income_id} not found"}
            
            # Build dynamic update query
            updates = []
            params = []
            
            if date is not None:
                updates.append("date = ?")
                params.append(date)
            if amount is not None:
                updates.append("amount = ?")
                params.append(amount)
            if source is not None:
                updates.append("source = ?")
                params.append(source)
            if note is not None:
                updates.append("note = ?")
                params.append(note)
            
            if not updates:
                return {"status": "error", "message": "No fields to update"}
            
            params.append(income_id)
            query = f"UPDATE income SET {', '.join(updates)} WHERE id = ?"
            await c.execute(query, params)
            await c.commit()
            
            return {"status": "ok", "id": income_id, "updated_fields": len(updates)}
    except Exception as e:
        return {"status": "error", "message": f"Error editing income: {str(e)}"}

@mcp.tool()
async def delete_income(income_id):
    """Delete an income entry by ID."""
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            # Check if income exists
            cur = await c.execute("SELECT * FROM income WHERE id = ?", (income_id,))
            if not await cur.fetchone():
                return {"status": "error", "message": f"Income with id {income_id} not found"}
            
            await c.execute("DELETE FROM income WHERE id = ?", (income_id,))
            await c.commit()
            return {"status": "ok", "id": income_id, "message": "Income deleted successfully"}
    except Exception as e:
        return {"status": "error", "message": f"Error deleting income: {str(e)}"}

# ============= ANALYSIS FUNCTIONS =============

@mcp.tool()
async def get_balance(start_date, end_date):
    """Calculate net balance (total income - total expenses) for a date range."""
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            # Get total expenses
            cur = await c.execute(
                "SELECT SUM(amount) FROM expenses WHERE date BETWEEN ? AND ?",
                (start_date, end_date)
            )
            result = await cur.fetchone()
            total_expenses = result[0] if result[0] is not None else 0
            
            # Get total income
            cur = await c.execute(
                "SELECT SUM(amount) FROM income WHERE date BETWEEN ? AND ?",
                (start_date, end_date)
            )
            result = await cur.fetchone()
            total_income = result[0] if result[0] is not None else 0
            
            balance = total_income - total_expenses
            
            return {
                "total_income": total_income,
                "total_expenses": total_expenses,
                "balance": balance,
                "start_date": start_date,
                "end_date": end_date
            }
    except Exception as e:
        return {"status": "error", "message": f"Error calculating balance: {str(e)}"}

@mcp.tool()
async def summarize(start_date, end_date, category=None):
    """Summarize expenses by category within an inclusive date range."""
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            query = """
                SELECT category, SUM(amount) AS total_amount, COUNT(*) as count
                FROM expenses
                WHERE date BETWEEN ? AND ?
            """
            params = [start_date, end_date]

            if category:
                query += " AND category = ?"
                params.append(category)

            query += " GROUP BY category ORDER BY total_amount DESC"

            cur = await c.execute(query, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in await cur.fetchall()]
    except Exception as e:
        return {"status": "error", "message": f"Error summarizing expenses: {str(e)}"}

# ============= RESOURCES =============

@mcp.resource("expense:///categories", mime_type="application/json")
def categories():
    """Provide expense categories."""
    try:
        default_categories = {
            "categories": [
                "Food & Dining",
                "Transportation",
                "Shopping",
                "Entertainment",
                "Bills & Utilities",
                "Healthcare",
                "Travel",
                "Education",
                "Business",
                "Other"
            ]
        }
        
        try:
            with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            import json
            return json.dumps(default_categories, indent=2)
    except Exception as e:
        return f'{{"error": "Could not load categories: {str(e)}"}}'

# Start the server
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
    # For stdio transport (Claude Desktop), use:
    # mcp.run()