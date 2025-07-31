from mysql.connector import connect, Error
from CONFIG import Config

def insert_user(telegram_id, name, email, password_hash, role):
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO `user` (`telegram_id`,`name`,`email`,`password_hash`,`role`) VALUES (%s,%s,%s,%s,%s)",
            (telegram_id, name, email, password_hash, role)
        )
        conn.commit()
        return cur.lastrowid
    except Error as e:
        print(f"[DML] insert_user error: {e}")
        return None
    finally:
        if conn and conn.is_connected():
            cur.close(); conn.close()

def email_exists(email):
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor()
        cur.execute("SELECT id FROM `user` WHERE `email`=%s", (email,))
        result = cur.fetchone()
        return result is not None
    except Error as e:
        print(f"[DML] email_exists error: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            cur.close(); conn.close()

def insert_skill(name, category):
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor()
        cur.execute("INSERT INTO `skill` (`name`,`category`) VALUES (%s,%s)", (name, category))
        conn.commit()
        return cur.lastrowid
    except Error as e:
        print(f"[DML] insert_skill error: {e}")
        return None
    finally:
        if conn and conn.is_connected():
            cur.close(); conn.close()

def insert_user_skill(user_id, skill_id, proficiency=1):
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor()
        cur.execute("INSERT INTO `user_skill` (`user_id`,`skill_id`,`proficiency`) VALUES (%s,%s,%s)",
                    (user_id, skill_id, proficiency))
        conn.commit()
        return True
    except Error as e:
        print(f"[DML] insert_user_skill error: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            cur.close(); conn.close()

def update_skill(skill_id, new_name, new_category):
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor()
        cur.execute("UPDATE `skill` SET `name`=%s, `category`=%s WHERE `id`=%s",
                    (new_name, new_category, skill_id))
        conn.commit()
        return cur.rowcount > 0
    except Error as e:
        print(f"[DML] update_skill error: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            cur.close(); conn.close()

def delete_skill(skill_id):
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor()
        cur.execute("DELETE FROM `skill` WHERE `id`=%s", (skill_id,))
        conn.commit()
        return cur.rowcount > 0
    except Error as e:
        print(f"[DML] delete_skill error: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            cur.close(); conn.close()

def insert_project(employer_id, title, description, category=None, role=None):
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor()
        if category and role:
            cur.execute("INSERT INTO `project` (`employer_id`,`title`,`description`,`category`,`role`) VALUES (%s,%s,%s,%s,%s)",
                        (employer_id, title, description, category, role))
        else:
            cur.execute("INSERT INTO `project` (`employer_id`,`title`,`description`) VALUES (%s,%s,%s)",
                        (employer_id, title, description))
        conn.commit()
        return cur.lastrowid
    except Error as e:
        print(f"[DML] insert_project error: {e}")
        return None
    finally:
        if conn and conn.is_connected():
            cur.close(); conn.close()

def update_project(project_id, new_title, new_description):
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor()
        cur.execute("UPDATE `project` SET `title`=%s, `description`=%s WHERE `id`=%s",
                    (new_title, new_description, project_id))
        conn.commit()
        return cur.rowcount > 0
    except Error as e:
        print(f"[DML] update_project error: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            cur.close(); conn.close()

def delete_project(project_id):
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor()
        cur.execute("DELETE FROM `project` WHERE `id`=%s", (project_id,))
        conn.commit()
        return cur.rowcount > 0
    except Error as e:
        print(f"[DML] delete_project error: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            cur.close(); conn.close()
    # افزودن پروژه با مدیریت خطای تکراری
def add_project(self, user_id, title, desc, category, role):
    with self.connection.cursor() as cursor:
            cursor.execute("SELECT id FROM project WHERE user_id=%s AND title=%s", (user_id, title))
            if cursor.fetchone():
                return "DUPLICATE"
            cursor.execute(
                "INSERT INTO project (user_id, title, description, category, role) VALUES (%s, %s, %s, %s, %s)",
                (user_id, title, desc, category, role)
            )
            self.connection.commit()
            return cursor.lastrowid


def add_skill(self, name, category, user_id):
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT id FROM skill WHERE name=%s AND category=%s AND user_id=%s", (name, category, user_id))
            if cursor.fetchone():
                return "DUPLICATE"
            cursor.execute(
                "INSERT INTO skill (name, category, user_id) VALUES (%s, %s, %s)",
                (name, category, user_id)
            )
            self.connection.commit()
            return cursor.lastrowid
