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

    @staticmethod
    def add_user(telegram_id, name, email, password_hash, role):
        from DML import insert_user
        return insert_user(telegram_id, name, email, password_hash, role)

    @staticmethod
    def email_exists(email):
        from DML import email_exists
        return email_exists(email)

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
    def add_project(employer_id, title, description, category=None, role=None):
        from DML import insert_project
        return insert_project(employer_id, title, description, category, role)

    @staticmethod
    def update_project(project_id, new_title, new_description):
        from DML import update_project
        return update_project(project_id, new_title, new_description)

    @staticmethod
    def delete_project(project_id):
        from DML import delete_project
        return delete_project(project_id)

    @staticmethod
    def find_user(telegram_id):
        from DQL import get_user_by_telegram_id
        return get_user_by_telegram_id(telegram_id)

    @staticmethod
    def get_user_by_id(user_id):
        from DQL import get_user_by_id
        return get_user_by_id(user_id)

    @staticmethod
    def list_user_skills(user_id):
        from DQL import get_user_skills
        return get_user_skills(user_id)

    @staticmethod
    def list_projects(employer_id):
        from DQL import get_projects_by_employer
        return get_projects_by_employer(employer_id)

    @staticmethod
    def list_my_accounts(telegram_id):
        from DQL import get_users_by_telegram_id
        return get_users_by_telegram_id(telegram_id)

    @staticmethod
    def close():
        if FreelanceBot._connection and FreelanceBot._connection.is_connected():
            FreelanceBot._connection.close()
            FreelanceBot._connection = None

    def get_user_profile(self, user_id):
        with self.connection.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM user WHERE id=%s", (user_id,))
            return cursor.fetchone()

    def update_user_profile(self, user_id, field, value):
        with self.connection.cursor() as cursor:
            sql = f"UPDATE user SET {field}=%s WHERE id=%s"
            cursor.execute(sql, (value, user_id))
            self.connection.commit()
            return cursor.rowcount > 0
    def get_user_profile(self, user_id):
        with self.connection.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM user WHERE id=%s", (user_id,))
            return cursor.fetchone()

    def update_user_profile(self, user_id, field, value):
        with self.connection.cursor() as cursor:
            sql = f"UPDATE user SET {field}=%s WHERE id=%s"
            cursor.execute(sql, (value, user_id))
            self.connection.commit()
            return cursor.rowcount > 0
