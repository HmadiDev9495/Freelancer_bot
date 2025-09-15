# DQL.py
from mysql.connector import connect, Error
from CONFIG import Config

def _conn():
    return connect(
        host=Config.DB_HOST, user=Config.DB_USER,
        password=Config.DB_PASSWORD, database=Config.DB_NAME,
        port=Config.DB_PORT
    )

def get_user_by_telegram_id(telegram_id):
    try:
        conn = _conn(); cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM `user` WHERE `telegram_id`=%s ORDER BY id DESC LIMIT 1", (telegram_id,))
        return cur.fetchone()
    except Error as e:
        print(f"[DQL] get_user_by_telegram_id error: {e}")
        return None
    finally:
        try:
            cur.close(); conn.close()
        except: pass

def get_users_by_telegram_id(telegram_id):
    try:
        conn = _conn(); cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM `user` WHERE `telegram_id`=%s ORDER BY id DESC", (telegram_id,))
        return cur.fetchall()
    except Error as e:
        print(f"[DQL] get_users_by_telegram_id error: {e}")
        return []
    finally:
        try:
            cur.close(); conn.close()
        except: pass

def get_user_by_id(user_id: int):
    try:
        conn = connect(host=Config.DB_HOST, user=Config.DB_USER,
                       password=Config.DB_PASSWORD, database=Config.DB_NAME, port=Config.DB_PORT)
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM `user` WHERE id=%s", (int(user_id),))
        return cur.fetchone()
    except Error as e:
        print(f"[DQL] get_user_by_id error: {e}")
        return None
    finally:
        try: cur.close(); conn.close()
        except: pass

def list_user_skills(user_id: int):
    from mysql.connector import connect, Error
    from CONFIG import Config
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT s.id, s.name, s.category, us.proficiency
            FROM user_skill us
            JOIN skill s ON s.id = us.skill_id
            WHERE us.user_id=%s
            ORDER BY s.category, s.name
        """, (user_id,))
        return cur.fetchall()
    except Error as e:
        print(f"[DQL] list_user_skills error: {e}")
        return []
    finally:
        try:
            cur.close(); conn.close()
        except:
            pass

def get_projects_by_employer(employer_id):
    try:
        conn = _conn(); cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT id, title, description, category, role, budget, delivery_days, created_at
            FROM project WHERE employer_id=%s
            ORDER BY id DESC
        """, (employer_id,))
        return cur.fetchall()
    except Error as e:
        print(f"[DQL] get_projects_by_employer error: {e}")
        return []
    finally:
        try:
            cur.close(); conn.close()
        except: pass

def get_user_skills(user_id):
    return list_user_skills(user_id)

def get_dashboard_stats(user_id: int):
    """
    آمار کلی داشبورد را می‌دهد.
    نیازمند ستون‌های budget/status/progress/updated_at در جدول project است.
    """
    try:
        conn = connect(host=Config.DB_HOST, user=Config.DB_USER,
                       password=Config.DB_PASSWORD, database=Config.DB_NAME,
                       port=Config.DB_PORT)
        cur = conn.cursor(dictionary=True)

        # تعداد کل پروژه‌ها
        cur.execute("SELECT COUNT(*) AS total FROM project WHERE employer_id=%s", (user_id,))
        total = (cur.fetchone() or {}).get("total", 0)

        # بودجه: مجموع/میانگین
        cur.execute("SELECT SUM(budget) AS budget_sum, AVG(budget) AS budget_avg FROM project WHERE employer_id=%s", (user_id,))
        b = cur.fetchone() or {}
        budget_sum = b.get("budget_sum")
        budget_avg = b.get("budget_avg")

        # آخرین ایجاد/بروزرسانی
        cur.execute(
            "SELECT MAX(created_at) AS last_created, MAX(updated_at) AS last_updated "
            "FROM project WHERE employer_id=%s", (user_id,)
        )
        t = cur.fetchone() or {}
        return {
            "projects_total": total,
            "budget_sum": budget_sum, "budget_avg": budget_avg,
            "last_project_created": t.get("last_created"),
            "last_project_updated": t.get("last_updated"),
        }
    except Error as e:
        print(f"[DQL] get_dashboard_stats error: {e}")
        return {
            "projects_total": 0, "budget_sum": None, "budget_avg": None,
            "last_project_created": None, "last_project_updated": None
        }
    finally:
        try:
            cur.close(); conn.close()
        except:
            pass

def get_projects_by_status(employer_id: int, status: str):
    from mysql.connector import connect, Error
    from CONFIG import Config
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT id, title, status, progress, budget, delivery_days, created_at, updated_at
            FROM project
            WHERE employer_id=%s AND status=%s
            ORDER BY id DESC
        """, (employer_id, status))
        return cur.fetchall()
    except Error as e:
        print(f"[DQL] get_projects_by_status error: {e}")
        return []
    finally:
        try:
            cur.close(); conn.close()
        except: pass

def get_top_skills(user_id: int, limit: int = 5):
    """
    برمی‌گرداند: لیست دیکشنری:
    [{'id':..., 'name':..., 'category':..., 'uses':n, 'avg_prof':x.x}, ...]
    """
    from mysql.connector import connect, Error
    from CONFIG import Config
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT
              s.id, s.name, s.category,
              COUNT(*) AS uses,
              AVG(us.proficiency) AS avg_prof
            FROM user_skill us
            JOIN skill s ON s.id = us.skill_id
            WHERE us.user_id = %s
            GROUP BY s.id, s.name, s.category
            ORDER BY uses DESC, avg_prof DESC, s.name ASC
            LIMIT %s
        """, (user_id, int(limit)))
        return cur.fetchall()
    except Error as e:
        print(f"[DQL] get_top_skills error: {e}")
        return []
    finally:
        try: cur.close(); conn.close()
        except: pass
def get_budget_stats(user_id: int):
    """
    برمی‌گرداند:
    {
      'avg_all': Decimal|None,
      'sum_all': Decimal|None,
      'avg_done': Decimal|None,
      'sum_done': Decimal|None,
      'count_done': int
    }
    """
    from mysql.connector import connect, Error
    from CONFIG import Config
    data = {'avg_all': None, 'sum_all': None, 'avg_done': None, 'sum_done': None, 'count_done': 0}
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor()

        cur.execute("""
          SELECT AVG(budget), SUM(budget)
          FROM project
          WHERE employer_id=%s AND budget IS NOT NULL
        """, (user_id,))
        r = cur.fetchone()
        if r: data['avg_all'], data['sum_all'] = r[0], r[1]

        cur.execute("""
          SELECT AVG(budget), SUM(budget), COUNT(*)
          FROM project
          WHERE employer_id=%s AND status='done' AND budget IS NOT NULL
        """, (user_id,))
        r = cur.fetchone()
        if r:
            data['avg_done'], data['sum_done'], data['count_done'] = r[0], r[1], int(r[2] or 0)

        return data
    except Error as e:
        print(f"[DQL] get_budget_stats error: {e}")
        return data
    finally:
        try: cur.close(); conn.close()
        except: pass
def get_recent_projects(user_id: int, limit: int = 5):
    from mysql.connector import connect, Error
    from CONFIG import Config
    try:
        conn = connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        cur = conn.cursor(dictionary=True)
        cur.execute("""
          SELECT id, title, status, progress, budget, delivery_days, created_at, updated_at
          FROM project
          WHERE employer_id=%s
          ORDER BY COALESCE(updated_at, created_at) DESC
          LIMIT %s
        """, (user_id, int(limit)))
        return cur.fetchall()
    except Error as e:
        print(f"[DQL] get_recent_projects error: {e}")
        return []
    finally:
        try: cur.close(); conn.close()
        except: pass
def list_registered_users(limit: int = 10):
    try:
        conn = connect(host=Config.DB_HOST, user=Config.DB_USER,
                       password=Config.DB_PASSWORD, database=Config.DB_NAME,
                       port=Config.DB_PORT)
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT id, name, email, telegram_id FROM `user` "
            "WHERE telegram_id IS NOT NULL ORDER BY id DESC LIMIT %s", (int(limit),)
        )
        return cur.fetchall()
    except Error as e:
        print(f"[DQL] list_registered_users error: {e}")
        return []
    finally:
        try: cur.close(); conn.close()
        except: pass

def list_users_by_telegram_id(telegram_id: int, limit: int = 10):
    try:
        conn = connect(host=Config.DB_HOST, user=Config.DB_USER,
                       password=Config.DB_PASSWORD, database=Config.DB_NAME,
                       port=Config.DB_PORT)
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT id, name, email, telegram_id, created_at "
            "FROM `user` WHERE telegram_id=%s ORDER BY id DESC LIMIT %s",
            (int(telegram_id), int(limit))
        )
        return cur.fetchall()
    except Error as e:
        print(f"[DQL] list_users_by_telegram_id error: {e}")
        return []
    finally:
        try: cur.close(); conn.close()
        except: pass
def count_users_by_telegram_id(telegram_id: int) -> int:
    try:
        conn = connect(host=Config.DB_HOST, user=Config.DB_USER,
                       password=Config.DB_PASSWORD, database=Config.DB_NAME,
                       port=Config.DB_PORT)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM `user` WHERE telegram_id=%s", (int(telegram_id),))
        row = cur.fetchone()
        return int(row[0]) if row else 0
    except Error as e:
        print(f"[DQL] count_users_by_telegram_id error: {e}")
        return 0
    finally:
        try: cur.close(); conn.close()
        except: pass
