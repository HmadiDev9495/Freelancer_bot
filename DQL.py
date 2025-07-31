from mysql.connector import connect, Error
from CONFIG import Config

def get_user_by_telegram_id(telegram_id):
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM `user` WHERE `telegram_id`=%s", (telegram_id,))
        return cur.fetchone()
    except Error as e:
        print(f"[DQL] get_user error: {e}")
        return None
    finally:
        if conn and conn.is_connected():
            cur.close(); conn.close()

def get_users_by_telegram_id(telegram_id):
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, name, email FROM `user` WHERE `telegram_id`=%s", (telegram_id,))
        return cur.fetchall()
    except Error as e:
        print(f"[DQL] get_users_by_telegram_id error: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            cur.close(); conn.close()

def get_user_by_id(user_id):
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM `user` WHERE `id`=%s", (user_id,))
        return cur.fetchone()
    except Error as e:
        print(f"[DQL] get_user_by_id error: {e}")
        return None
    finally:
        if conn and conn.is_connected():
            cur.close(); conn.close()

def get_user_skills(user_id):
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT sk.id, sk.name, sk.category, us.proficiency
            FROM user_skill us
            JOIN skill sk ON us.skill_id=sk.id
            WHERE us.user_id=%s
            """, (user_id,)
        )
        return cur.fetchall()
    except Error as e:
        print(f"[DQL] get_user_skills error: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            cur.close(); conn.close()

def get_projects_by_employer(employer_id):
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT id, title, description, created_at "
            "FROM project WHERE employer_id=%s", (employer_id,)
        )
        return cur.fetchall()
    except Error as e:
        print(f"[DQL] get_projects_by_employer error: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            cur.close(); conn.close()
