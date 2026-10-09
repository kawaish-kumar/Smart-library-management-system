
from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app)

DATABASE = "library.db"


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def read_request_data():
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict()


def create_database():
    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'student'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            category TEXT,
            available INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS borrowings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            book_id INTEGER NOT NULL,
            borrow_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            return_date TEXT,
            status TEXT DEFAULT 'Borrowed'
        )
    """)

    connection.commit()
    connection.close()


def create_admin():
    connection = get_db()
    cursor = connection.cursor()

    email = "kawe12@admin.com"
    password = "kawe34"

    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    admin = cursor.fetchone()

    if admin:
        cursor.execute("""
            UPDATE users
            SET name = ?, password = ?, role = 'admin'
            WHERE email = ?
        """, ("Admin", generate_password_hash(password), email))
    else:
        cursor.execute("""
            INSERT INTO users (name, email, password, role)
            VALUES (?, ?, ?, 'admin')
        """, ("Admin", email, generate_password_hash(password)))

    connection.commit()
    connection.close()


@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Smart Library backend is running"})


@app.route("/api/books", methods=["GET"])
def get_books():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()

    connection = get_db()
    cursor = connection.cursor()

    query = "SELECT * FROM books WHERE 1=1"
    values = []

    if search:
        query += " AND (title LIKE ? OR author LIKE ?)"
        values.extend([f"%{search}%", f"%{search}%"])

    if category:
        query += " AND category = ?"
        values.append(category)

    cursor.execute(query, values)
    books = [dict(row) for row in cursor.fetchall()]
    connection.close()

    return jsonify(books)


@app.route("/api/books", methods=["POST"])
def add_book():
    data = read_request_data()

    title = data.get("title", "").strip()
    author = data.get("author", "").strip()
    category = data.get("category", "").strip()

    if not title or not author:
        return jsonify({"error": "Title and author are required"}), 400

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO books (title, author, category, available)
        VALUES (?, ?, ?, 1)
    """, (title, author, category))

    connection.commit()
    book_id = cursor.lastrowid
    connection.close()

    return jsonify({
        "message": "Book added successfully",
        "id": book_id
    }), 201


@app.route("/api/books/<int:book_id>", methods=["DELETE"])
def delete_book(book_id):
    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("SELECT id FROM books WHERE id = ?", (book_id,))
    book = cursor.fetchone()

    if not book:
        connection.close()
        return jsonify({"error": "Book not found"}), 404

    cursor.execute("""
        SELECT id FROM borrowings
        WHERE book_id = ? AND LOWER(status) = 'borrowed'
    """, (book_id,))

    if cursor.fetchone():
        connection.close()
        return jsonify({
            "error": "Cannot delete a borrowed book"
        }), 400

    cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
    connection.commit()
    connection.close()

    return jsonify({"message": "Book deleted successfully"})


@app.route("/api/signup", methods=["POST"])
@app.route("/signup", methods=["POST"])
def signup():
    data = read_request_data()

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not name or not email or not password:
        return jsonify({"error": "Please fill in all fields"}), 400

    if len(password) < 6:
        return jsonify({
            "error": "Password must be at least 6 characters"
        }), 400

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))

    if cursor.fetchone():
        connection.close()
        return jsonify({"error": "Email already registered"}), 409

    cursor.execute("""
        INSERT INTO users (name, email, password, role)
        VALUES (?, ?, ?, 'student')
    """, (name, email, generate_password_hash(password)))

    connection.commit()
    user_id = cursor.lastrowid
    connection.close()

    return jsonify({
        "message": "Signup successful",
        "user_id": user_id
    }), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = read_request_data()

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    connection.close()

    if user and check_password_hash(user["password"], password):
        return jsonify({
            "message": "Login successful",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"]
            }
        })

    return jsonify({"error": "Invalid email or password"}), 401


@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = read_request_data()

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT * FROM users
        WHERE email = ? AND role = 'admin'
    """, (email,))

    admin = cursor.fetchone()
    connection.close()

    if admin and check_password_hash(admin["password"], password):
        return jsonify({
            "message": "Admin login successful",
            "user": {
                "id": admin["id"],
                "name": admin["name"],
                "email": admin["email"],
                "role": admin["role"]
            }
        })

    return jsonify({"error": "Invalid admin credentials"}), 401


@app.route("/api/users", methods=["GET"])
def get_users():
    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name, email, role
        FROM users
        ORDER BY id DESC
    """)

    users = [dict(row) for row in cursor.fetchall()]
    connection.close()

    return jsonify(users)


@app.route("/api/borrow", methods=["POST"])
def borrow_book():
    data = read_request_data()

    user_id = data.get("user_id")
    user_email = data.get("user_email") or data.get("email")
    book_id = data.get("book_id")

    if not book_id or (not user_id and not user_email):
        return jsonify({
            "error": "User and book are required"
        }), 400

    connection = get_db()
    cursor = connection.cursor()

    if user_email:
        user_email = user_email.strip().lower()
        cursor.execute(
            "SELECT email FROM users WHERE LOWER(email) = ?",
            (user_email,)
        )
    else:
        cursor.execute(
            "SELECT email FROM users WHERE id = ?",
            (user_id,)
        )

    user = cursor.fetchone()

    if not user:
        connection.close()
        return jsonify({"error": "User not found"}), 404

    cursor.execute(
        "SELECT id, available FROM books WHERE id = ?",
        (book_id,)
    )
    book = cursor.fetchone()

    if not book:
        connection.close()
        return jsonify({"error": "Book not found"}), 404

    if not book["available"]:
        connection.close()
        return jsonify({"error": "Book is not available"}), 400

    borrow_date = datetime.now().strftime("%Y-%m-%d")
    due_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

    cursor.execute("""
        INSERT INTO borrowings
        (user_email, book_id, borrow_date, due_date, status)
        VALUES (?, ?, ?, ?, 'Borrowed')
    """, (user["email"], book_id, borrow_date, due_date))

    cursor.execute(
        "UPDATE books SET available = 0 WHERE id = ?",
        (book_id,)
    )

    connection.commit()
    borrowing_id = cursor.lastrowid
    connection.close()

    return jsonify({
        "message": "Book borrowed successfully",
        "borrowing_id": borrowing_id
    }), 201


@app.route("/api/borrowings", methods=["GET"])
def get_borrowings():
    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            b.id,
            b.user_email,
            u.name AS user_name,
            b.book_id,
            bk.title AS book_title,
            b.borrow_date,
            b.due_date,
            b.return_date,
            b.status
        FROM borrowings b
        LEFT JOIN users u ON LOWER(b.user_email) = LOWER(u.email)
        LEFT JOIN books bk ON b.book_id = bk.id
        ORDER BY b.id DESC
    """)

    borrowings = [dict(row) for row in cursor.fetchall()]
    connection.close()

    return jsonify(borrowings)


@app.route("/api/return", methods=["POST"])
def return_book():
    data = read_request_data()
    borrowing_id = data.get("borrowing_id")

    if not borrowing_id:
        return jsonify({"error": "Borrowing ID is required"}), 400

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT book_id, status
        FROM borrowings
        WHERE id = ?
    """, (borrowing_id,))

    borrowing = cursor.fetchone()

    if not borrowing:
        connection.close()
        return jsonify({"error": "Borrowing record not found"}), 404

    if str(borrowing["status"]).lower() == "returned":
        connection.close()
        return jsonify({"error": "Book already returned"}), 400

    return_date = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        UPDATE borrowings
        SET status = 'Returned', return_date = ?
        WHERE id = ?
    """, (return_date, borrowing_id))

    cursor.execute("""
        UPDATE books SET available = 1 WHERE id = ?
    """, (borrowing["book_id"],))

    connection.commit()
    connection.close()

    return jsonify({"message": "Book returned successfully"})


if __name__ == "__main__":
    create_database()
    create_admin()
    app.run(debug=True, host="127.0.0.1", port=5000)
