import psycopg2

def get_connection():
    return psycopg2.connect(
        dbname="tree_db",
        user="tree_user",
        password="password123",
        host="localhost",
        port="5432"
    )

# =========================
# DETECT FUNCTION
# =========================
def detect_tree(image_path):
    return {
        "tree": "Neem",
        "confidence": 0.92
    }

# =========================
# COMPARE FUNCTION
# =========================
def compare_trees(before_path, after_path):
    return {
        "similarity": 0.85,
        "status": "improved"
    }