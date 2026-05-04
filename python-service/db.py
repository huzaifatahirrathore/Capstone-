import psycopg2

def get_connection():
    return psycopg2.connect(
        dbname="tree_db",
        user="tree_user",
        password="password123",
        host="localhost",
        port="5432"
    )