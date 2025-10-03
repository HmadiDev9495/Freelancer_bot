# Database.py
import mysql.connector
from mysql.connector import Error
from CONFIG import Config
import logging

logger = logging.getLogger("freelance-bot")

class FreelanceBot:
    def __init__(self):
        self.config = Config

    def _get_connection(self):
        """هر بار یک connection جدید و موقت ایجاد می‌کند — ایمن برای تلگرام."""
        return mysql.connector.connect(
            host=self.config.DB_HOST,
            user=self.config.DB_USER,
            password=self.config.DB_PASSWORD,
            database=self.config.DB_NAME,
            port=self.config.DB_PORT,
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci',
            autocommit=True
        )

    def find_user(self, telegram_id: int):
        try:
            conn = self._get_connection()
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM user WHERE telegram_id = %s", (telegram_id,))
            user = cur.fetchone()
            cur.close()
            conn.close()
            return user
        except Error as e:
            logger.error(f"DB Error in find_user: {e}")
            return None

    def add_user(self, telegram_id: int, name: str, email: str, password_hash: str, role: str):
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO user (telegram_id, name, email, password_hash, role)
                VALUES (%s, %s, %s, %s, %s)
            """, (telegram_id, name, email, password_hash, role))
            uid = cur.lastrowid
            cur.close()
            conn.close()
            return uid
        except Error as e:
            logger.error(f"DB Error in add_user: {e}")
            return None

    def update_user_profile(self, user_id: int, field: str, value):
        allowed_fields = {
            'name', 'email', 'role', 'bio', 'hourly_rate',
            'phone', 'linkedin', 'github', 'website',
            'password_hash'  # ✅ اضافه شد
        }
        if field not in allowed_fields:
            return False
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(f"UPDATE user SET `{field}` = %s WHERE id = %s", (value, user_id))
            cur.close()
            conn.close()
            return True
        except Error as e:
            logger.error(f"DB Error in update_user_profile: {e}")
            return False

    def add_skill(self, name: str, category: str):
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("INSERT IGNORE INTO skill (name, category) VALUES (%s, %s)", (name, category))
            if cur.rowcount == 0:
                cur.execute("SELECT id FROM skill WHERE name = %s AND category = %s", (name, category))
                row = cur.fetchone()
                skill_id = row[0] if row else None
            else:
                skill_id = cur.lastrowid
            cur.close()
            conn.close()
            return skill_id
        except Error as e:
            logger.error(f"DB Error in add_skill: {e}")
            return None

    def add_user_skill(self, user_id: int, skill_id: int, proficiency: int = 1):
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO user_skill (user_id, skill_id, proficiency)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE proficiency = VALUES(proficiency)
            """, (user_id, skill_id, proficiency))
            cur.close()
            conn.close()
            return True
        except Error as e:
            logger.error(f"DB Error in add_user_skill: {e}")
            return False

    def list_user_skills(self, user_id: int):
        try:
            conn = self._get_connection()
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT s.name, s.category, us.proficiency
                FROM user_skill us
                JOIN skill s ON us.skill_id = s.id
                WHERE us.user_id = %s
            """, (user_id,))
            skills = cur.fetchall()
            cur.close()
            conn.close()
            return skills
        except Error as e:
            logger.error(f"DB Error in list_user_skills: {e}")
            return []

    def add_project(self, employer_id: int, title: str, description: str = None,
                    category: str = None, budget: float = None, delivery_days: int = None):
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO project (employer_id, title, description, category, budget, delivery_days)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (employer_id, title, description, category, budget, delivery_days))
            pid = cur.lastrowid
            cur.close()
            conn.close()
            return pid
        except Error as e:
            if e.errno == 1062:  # Duplicate entry
                return "DUPLICATE"
            logger.error(f"DB Error in add_project: {e}")
            return None

    # --- توابع مورد استفاده در Main.py ---
    def get_projects_by_employer(self, user_id: int):
        try:
            conn = self._get_connection()
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM project WHERE employer_id = %s ORDER BY created_at DESC", (user_id,))
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return rows
        except Error as e:
            logger.error(f"DB Error in get_projects_by_employer: {e}")
            return []

    def projects_by_status(self, user_id: int, status: str):
        try:
            conn = self._get_connection()
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM project WHERE employer_id = %s AND status = %s ORDER BY created_at DESC", (user_id, status))
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return rows
        except Error as e:
            logger.error(f"DB Error in projects_by_status: {e}")
            return []

    def count_projects_by_owner(self, user_id: int):
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM project WHERE employer_id = %s", (user_id,))
            count = cur.fetchone()[0]
            cur.close()
            conn.close()
            return count
        except Error as e:
            logger.error(f"DB Error in count_projects_by_owner: {e}")
            return 0

    def count_all_users(self):
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM user")
            count = cur.fetchone()[0]
            cur.close()
            conn.close()
            return count
        except Error as e:
            logger.error(f"DB Error in count_all_users: {e}")
            return 0

    def count_projects_by_owner_and_status(self, user_id: int, status: str):
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM project WHERE employer_id = %s AND status = %s", (user_id, status))
            count = cur.fetchone()[0]
            cur.close()
            conn.close()
            return count
        except Error as e:
            logger.error(f"DB Error in count_projects_by_owner_and_status: {e}")
            return 0

    def recent_projects(self, user_id: int, limit: int = 5):
        try:
            conn = self._get_connection()
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT id, title, status, budget, progress, created_at, updated_at
                FROM project
                WHERE employer_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (user_id, limit))
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return rows
        except Error as e:
            logger.error(f"DB Error in recent_projects: {e}")
            return []

    def dashboard_stats(self, user_id: int):
        try:
            conn = self._get_connection()
            cur = conn.cursor(dictionary=True)
            # تعداد کل پروژه‌ها
            cur.execute("SELECT COUNT(*) AS total FROM project WHERE employer_id = %s", (user_id,))
            total = cur.fetchone()['total']
            # تعداد بر اساس وضعیت
            cur.execute("""
                SELECT status, COUNT(*) AS cnt
                FROM project
                WHERE employer_id = %s
                GROUP BY status
            """, (user_id,))
            by_status = {row['status']: row['cnt'] for row in cur.fetchall()}
            for s in ['draft', 'open', 'in_progress', 'done', 'cancelled']:
                by_status.setdefault(s, 0)
            # بودجه
            cur.execute("""
                SELECT SUM(budget) AS budget_sum, AVG(budget) AS budget_avg
                FROM project
                WHERE employer_id = %s AND budget IS NOT NULL
            """, (user_id,))
            budget = cur.fetchone()
            # مهارت‌ها
            cur.execute("SELECT COUNT(*) AS skills_total FROM user_skill WHERE user_id = %s", (user_id,))
            skills_total = cur.fetchone()['skills_total']
            cur.close()
            conn.close()
            return {
                'projects_total': total,
                'by_status': by_status,
                'budget_sum': float(budget['budget_sum']) if budget['budget_sum'] else 0,
                'budget_avg': float(budget['budget_avg']) if budget['budget_avg'] else 0,
                'skills_total': skills_total
            }
        except Error as e:
            logger.error(f"DB Error in dashboard_stats: {e}")
            return {
                'projects_total': 0,
                'by_status': {s: 0 for s in ['draft', 'open', 'in_progress', 'done', 'cancelled']},
                'budget_sum': 0,
                'budget_avg': 0,
                'skills_total': 0
            }

    def get_top_skills(self, user_id: int, limit: int = 3):
        try:
            conn = self._get_connection()
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT s.name, s.category, COUNT(*) AS uses, AVG(us.proficiency) AS avg_prof
                FROM user_skill us
                JOIN skill s ON us.skill_id = s.id
                WHERE us.user_id = %s
                GROUP BY s.id
                ORDER BY uses DESC
                LIMIT %s
            """, (user_id, limit))
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return rows
        except Error as e:
            logger.error(f"DB Error in get_top_skills: {e}")
            return []

    def budget_stats(self, user_id: int):
        try:
            conn = self._get_connection()
            cur = conn.cursor(dictionary=True)
            # کل
            cur.execute("SELECT SUM(budget) AS sum_all, AVG(budget) AS avg_all, COUNT(*) AS count_all FROM project WHERE employer_id = %s AND budget IS NOT NULL", (user_id,))
            all_stats = cur.fetchone()
            # تمام‌شده
            cur.execute("SELECT SUM(budget) AS sum_done, AVG(budget) AS avg_done, COUNT(*) AS count_done FROM project WHERE employer_id = %s AND status = 'done' AND budget IS NOT NULL", (user_id,))
            done_stats = cur.fetchone()
            cur.close()
            conn.close()
            return {
                'sum_all': float(all_stats['sum_all']) if all_stats['sum_all'] else 0,
                'avg_all': float(all_stats['avg_all']) if all_stats['avg_all'] else 0,
                'sum_done': float(done_stats['sum_done']) if done_stats['sum_done'] else 0,
                'avg_done': float(done_stats['avg_done']) if done_stats['avg_done'] else 0,
                'count_done': done_stats['count_done'] or 0
            }
        except Error as e:
            logger.error(f"DB Error in budget_stats: {e}")
            return {'sum_all': 0, 'avg_all': 0, 'sum_done': 0, 'avg_done': 0, 'count_done': 0}

    def list_all_skills(self):
        try:
            conn = self._get_connection()
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM skill")
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return rows
        except Error as e:
            logger.error(f"DB Error in list_all_skills: {e}")
            return []

    def update_skill(self, skill_id: int, name: str, category: str):
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("UPDATE skill SET name = %s, category = %s WHERE id = %s", (name, category, skill_id))
            cur.close()
            conn.close()
            return cur.rowcount > 0
        except Error as e:
            logger.error(f"DB Error in update_skill: {e}")
            return False

    def remove_user_skill(self, user_id: int, skill_id: int):
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM user_skill WHERE user_id = %s AND skill_id = %s", (user_id, skill_id))
            cur.close()
            conn.close()
            return cur.rowcount > 0
        except Error as e:
            logger.error(f"DB Error in remove_user_skill: {e}")
            return False

    def list_projects_filtered(self, status: str = "all", limit: int = 10, offset: int = 0):
        try:
            conn = self._get_connection()
            cur = conn.cursor(dictionary=True)
            if status == "all" or not status:
                cur.execute("SELECT * FROM project ORDER BY created_at DESC LIMIT %s OFFSET %s", (limit, offset))
            else:
                cur.execute("SELECT * FROM project WHERE status = %s ORDER BY created_at DESC LIMIT %s OFFSET %s", (status, limit, offset))
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return rows
        except Error as e:
            logger.error(f"DB Error in list_projects_filtered: {e}")
            return []