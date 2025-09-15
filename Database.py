# Database.py
from mysql.connector import connect
from CONFIG import Config
from DDL import create_tables

class FreelanceBot:
    _connection = None

    def __init__(self):
        if FreelanceBot._connection is None:
            create_tables()
            FreelanceBot._connection = connect(
                host=Config.DB_HOST, user=Config.DB_USER,
                password=Config.DB_PASSWORD, database=Config.DB_NAME,
                port=Config.DB_PORT
            )

    @property
    def connection(self):
        return FreelanceBot._connection

    # ---------- Users
    @staticmethod
    def add_user(telegram_id, name, email, password_hash, role):
        from DML import insert_user
        return insert_user(telegram_id, name, email, password_hash, role)

    @staticmethod
    def email_exists(email):
        from DML import email_exists
        return email_exists(email)

    @staticmethod
    def find_user(telegram_id):
        from DQL import get_user_by_telegram_id
        return get_user_by_telegram_id(telegram_id)

    def get_user_profile(self, user_id):
        with self.connection.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM user WHERE id=%s", (user_id,))
            return cursor.fetchone()

    def update_user_profile(self, user_id, field, value):
        # Allow-list برای جلوگیری از تزریق در نام ستون
        allowed = {
            'name', 'email', 'role', 'rating', 'profile_picture', 'bio', 'hourly_rate',
            'phone', 'linkedin', 'github', 'website'
        }
        if field not in allowed:
            return False
        with self.connection.cursor() as cursor:
            sql = f"UPDATE `user` SET `{field}`=%s WHERE id=%s"
            cursor.execute(sql, (value, user_id))
            self.connection.commit()
            return cursor.rowcount > 0

    @staticmethod
    def list_registered_users(limit: int = 10):
        from DQL import list_registered_users
        return list_registered_users(limit)

    @staticmethod
    def get_user_by_id(user_id: int):
        from DQL import get_user_by_id
        return get_user_by_id(user_id)

    # ---------- Skills
    @staticmethod
    def add_skill(name, category):
        from DML import insert_skill
        return insert_skill(name, category)

    @staticmethod
    def add_user_skill(user_id, skill_id, proficiency=1):
        from DML import insert_user_skill
        return insert_user_skill(user_id, skill_id, proficiency)

    @staticmethod
    def update_skill(skill_id, new_name, new_category):
        from DML import update_skill
        return update_skill(skill_id, new_name, new_category)

    @staticmethod
    def delete_skill(skill_id):
        from DML import delete_skill
        return delete_skill(skill_id)

    @staticmethod
    def list_user_skills(user_id):
        from DQL import list_user_skills as dql_list_user_skills
        return dql_list_user_skills(user_id=user_id)

    # ---------- Projects
    @staticmethod
    def add_project(employer_id, title, description, category=None, role=None, budget=None, delivery_days=None):
        from DML import insert_project
        return insert_project(employer_id, title, description, category, role, budget, delivery_days)

    @staticmethod
    def update_project(project_id, new_title, new_description):
        from DML import update_project
        return update_project(project_id, new_title, new_description)

    @staticmethod
    def delete_project(project_id):
        from DML import delete_project
        return delete_project(project_id)

    @staticmethod
    def list_projects(employer_id):
        from DQL import get_projects_by_employer
        return get_projects_by_employer(employer_id)

    @staticmethod
    def update_user_skill_proficiency(user_id: int, skill_id: int, proficiency: int):
        from DML import update_user_skill_proficiency
        return update_user_skill_proficiency(user_id, skill_id, proficiency)

    @staticmethod
    def delete_user_skill(user_id: int, skill_id: int):
        from DML import delete_user_skill
        return delete_user_skill(user_id, skill_id)

    @staticmethod
    def list_my_accounts(telegram_id):
        from DQL import get_users_by_telegram_id
        return get_users_by_telegram_id(telegram_id)

    # ---------- Dashboard / Reports
    @staticmethod
    def dashboard_stats(user_id:int):
        from DQL import get_dashboard_stats
        return get_dashboard_stats(user_id)

    @staticmethod
    def projects_by_status(employer_id:int, status:str):
        from DQL import get_projects_by_status
        return get_projects_by_status(employer_id, status)

    @staticmethod
    def set_project_status(project_id:int, status:str=None, progress:int=None):
        from DML import update_project_status
        return update_project_status(project_id, status, progress)

    @staticmethod
    def top_skills(user_id: int, limit: int = 5):
        from DQL import get_top_skills
        return get_top_skills(user_id, limit)

    @staticmethod
    def budget_stats(user_id: int):
        from DQL import get_budget_stats
        return get_budget_stats(user_id)

    @staticmethod
    def recent_projects(user_id: int, limit: int = 5):
        from DQL import get_recent_projects
        return get_recent_projects(user_id, limit)

    @staticmethod
    def close():
        if FreelanceBot._connection and FreelanceBot._connection.is_connected():
            FreelanceBot._connection.close()
            FreelanceBot._connection = None
    @staticmethod
    def list_users_by_telegram_id(telegram_id: int, limit: int = 10):
        from DQL import list_users_by_telegram_id
        return list_users_by_telegram_id(telegram_id, limit)
    @staticmethod
    def count_users_by_telegram_id(telegram_id: int) -> int:
        from DQL import count_users_by_telegram_id
        return count_users_by_telegram_id(telegram_id)
