import psycopg2

def get_connection():
    return psycopg2.connect(
        dbname="tree_db",
        user="tree_user",
        password="password123",
        host="localhost",
        port="5432"
    )
# ────────────────
# USER CRUD FUNCTIONS
# ────────────────
def create_user(username, email, password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (username, email, password)
        VALUES (%s, %s, %s)
        RETURNING id, username, email
    """, (username, email, password))
    user = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return user

def get_user(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, email FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user

def get_all_users():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, email FROM users")
    users = cur.fetchall()
    cur.close()
    conn.close()
    return users

def update_user(user_id, username, email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users SET username = %s, email = %s WHERE id = %s
        RETURNING id, username, email
    """, (username, email, user_id))
    user = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return user

def delete_user(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = %s RETURNING id", (user_id,))
    deleted = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return deleted


# ────────────────
# USER SIGNUP & LOGIN HELPERS (PYTHON)
# ────────────────
def signup_user(username, email, password):
    conn = get_connection()
    cur = conn.cursor()
    # Check if email exists
    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    if cur.fetchone():
        cur.close()
        conn.close()
        return None  # Email already exists
    cur.execute("""
        INSERT INTO users (username, email, password)
        VALUES (%s, %s, %s)
        RETURNING id, username, email
    """, (username, email, password))
    user = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return user

def login_user(email, password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, email FROM users WHERE email = %s AND password = %s", (email, password))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user