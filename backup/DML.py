from mysql.connector import connect, Error
from CONFIG import Config
from typing import Optional


# ---- Users
def insert_user(telegram_id, name, email, password_hash, role):
    try:
        conn = connect(host=Config.DB_HOST, user=Config.DB_USER,
                       password=Config.DB_PASSWORD, database=Config.DB_NAME,
                       port=Config.DB_PORT)
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
        conn = connect(host=Config.DB_HOST, user=Config.DB_USER,
                       password=Config.DB_PASSWORD, database=Config.DB_NAME,
                       port=Config.DB_PORT)
        cur = conn.cursor()
        cur.execute("SELECT id FROM `user` WHERE `email`=%s", (email,))
        return cur.fetchone() is not None
    except Error as e:
        print(f"[DML] email_exists error: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            cur.close(); conn.close()

# ---- Skills
def insert_skill(name, category):
    try:
        conn = connect(host=Config.DB_HOST, user=Config.DB_USER,
                       password=Config.DB_PASSWORD, database=Config.DB_NAME,
                       port=Config.DB_PORT)
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
        conn = connect(host=Config.DB_HOST, user=Config.DB_USER,
                       password=Config.DB_PASSWORD, database=Config.DB_NAME,
                       port=Config.DB_PORT)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO `user_skill` (`user_id`,`skill_id`,`proficiency`) VALUES (%s,%s,%s)",
            (user_id, skill_id, proficiency)
        )
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
        conn = connect(host=Config.DB_HOST, user=Config.DB_USER,
                       password=Config.DB_PASSWORD, database=Config.DB_NAME,
                       port=Config.DB_PORT)
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
        conn = connect(host=Config.DB_HOST, user=Config.DB_USER,
                       password=Config.DB_PASSWORD, database=Config.DB_NAME,
                       port=Config.DB_PORT)
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

# ---- Projects
def insert_project(employer_id, title, description, category=None, role=None, budget=None, delivery_days=None):
    try:
        conn = connect(host=Config.DB_HOST, user=Config.DB_USER,
                       password=Config.DB_PASSWORD, database=Config.DB_NAME,
                       port=Config.DB_PORT)
        cur = conn.cursor()

        # check duplicate per (employer_id, title)
        cur.execute("SELECT id FROM `project` WHERE `employer_id`=%s AND `title`=%s", (employer_id, title))
        if cur.fetchone():
            return "DUPLICATE"

        if category is not None or role is not None or budget is not None or delivery_days is not None:
            cur.execute(
                "INSERT INTO `project` (`employer_id`,`title`,`description`,`category`,`role`,`budget`,`delivery_days`) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (employer_id, title, description, category, role, budget, delivery_days)
            )
        else:
            cur.execute(
                "INSERT INTO `project` (`employer_id`,`title`,`description`) VALUES (%s,%s,%s)",
                (employer_id, title, description)
            )
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
        conn = connect(host=Config.DB_HOST, user=Config.DB_USER,
                       password=Config.DB_PASSWORD, database=Config.DB_NAME,
                       port=Config.DB_PORT)
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
        conn = connect(host=Config.DB_HOST, user=Config.DB_USER,
                       password=Config.DB_PASSWORD, database=Config.DB_NAME,
                       port=Config.DB_PORT)
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

def update_project_status(project_id: int,
                          status: Optional[str] = None,
                          progress: Optional[int] = None) -> bool:
    """
    وضعیت/پیشرفت پروژه را آپدیت می‌کند.
    True اگر حداقل یک ردیف تغییر کند، وگرنه False.
    """
    conn = None
    cur = None
    try:
        conn = connect(host=Config.DB_HOST, user=Config.DB_USER,
                       password=Config.DB_PASSWORD, database=Config.DB_NAME,
                       port=Config.DB_PORT)
        cur = conn.cursor()

        # فهرست فیلدهایی که واقعاً قرار است آپدیت شوند را بساز
        sets = []
        params = []
        if status is not None:
            sets.append("status=%s")
            params.append(status)
        if progress is not None:
            sets.append("progress=%s")
            params.append(int(progress))

        # اگر هیچ فیلدی برای آپدیت نداشتیم، بی‌خودی SQL نزنیم
        if not sets:
            return False

        # به‌روز کردن زمان آخرین تغییر (اختیاری ولی خوبه)
        sets.append("updated_at=NOW()")

        params.append(int(project_id))
        sql = f"UPDATE project SET {', '.join(sets)} WHERE id=%s"
        cur.execute(sql, tuple(params))
        conn.commit()
        return cur.rowcount > 0

    except Error as e:
        print(f"[DML] update_project_status error: {e}")
        return False

    finally:
        # فقط جمع‌کردن ارتباط؛ اینجا return نکن
        try:
            if cur: cur.close()
            if conn: conn.close()
        except:
            pass

def update_user_skill_proficiency(user_id: int, skill_id: int, proficiency: int):
    try:
        conn = connect(host=Config.DB_HOST, user=Config.DB_USER,
                       password=Config.DB_PASSWORD, database=Config.DB_NAME,
                       port=Config.DB_PORT)
        cur = conn.cursor()
        cur.execute(
            "UPDATE user_skill SET proficiency=%s WHERE user_id=%s AND skill_id=%s",
            (int(proficiency), int(user_id), int(skill_id))
        )
        conn.commit()
        return cur.rowcount > 0
    except Error as e:
        print(f"[DML] update_user_skill_proficiency error: {e}")
        return False
    finally:
        try:
            cur.close(); conn.close()
        except:
            pass


def delete_user_skill(user_id: int, skill_id: int):
    try:
        conn = connect(host=Config.DB_HOST, user=Config.DB_USER,
                       password=Config.DB_PASSWORD, database=Config.DB_NAME,
                       port=Config.DB_PORT)
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM user_skill WHERE user_id=%s AND skill_id=%s",
            (int(user_id), int(skill_id))
        )
        conn.commit()
        return cur.rowcount > 0
    except Error as e:
        print(f"[DML] delete_user_skill error: {e}")
        return False
    finally:
        try:
            cur.close(); conn.close()
        except:
            pass
