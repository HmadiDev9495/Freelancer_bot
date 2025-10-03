# DDL.py: Script to create and manage database schema
import mysql.connector
from mysql.connector import Error
from CONFIG import Config

def create_database():
    """Create the database if it doesn't exist."""
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            port=Config.DB_PORT
        )
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cur.close()
        conn.close()
        print(f"Database '{Config.DB_NAME}' created or already exists.")
    except Error as e:
        print(f"Error creating database: {e}")

def index_exists(cur, table: str, index_name: str) -> bool:
    cur.execute("""
        SELECT COUNT(1)
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND index_name = %s
    """, (table, index_name))
    return cur.fetchone()[0] > 0

def create_tables():
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            port=Config.DB_PORT,
            autocommit=False
        )
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS `user` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `telegram_id` BIGINT UNIQUE NOT NULL,
                `name` VARCHAR(100) NOT NULL,
                `email` VARCHAR(100) UNIQUE NOT NULL,
                `password_hash` VARCHAR(255) NOT NULL,
                `role` ENUM('employer','freelancer') NOT NULL,
                `bio` TEXT DEFAULT NULL,
                `hourly_rate` DECIMAL(10,2) DEFAULT NULL,
                `phone` VARCHAR(20) DEFAULT NULL,
                `linkedin` VARCHAR(255) DEFAULT NULL,
                `github` VARCHAR(255) DEFAULT NULL,
                `website` VARCHAR(255) DEFAULT NULL,
                `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS `skill` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `name` VARCHAR(100) UNIQUE NOT NULL,
                `category` VARCHAR(100) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS `user_skill` (
                `user_id` INT NOT NULL,
                `skill_id` INT NOT NULL,
                `proficiency` TINYINT UNSIGNED DEFAULT 1,
                PRIMARY KEY (`user_id`, `skill_id`),
                FOREIGN KEY (`user_id`) REFERENCES `user`(`id`) ON DELETE CASCADE,
                FOREIGN KEY (`skill_id`) REFERENCES `skill`(`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS `project` (
                `id` INT NOT NULL AUTO_INCREMENT,
                `employer_id` INT NOT NULL,
                `title` VARCHAR(255) NOT NULL,
                `description` TEXT,
                `category` VARCHAR(100) DEFAULT NULL,
                `budget` DECIMAL(12,2) DEFAULT NULL,
                `delivery_days` INT DEFAULT NULL,
                `status` ENUM('draft','open','in_progress','done','cancelled') NOT NULL DEFAULT 'draft',
                `progress` TINYINT UNSIGNED DEFAULT 0,
                `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                `updated_at` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                FOREIGN KEY (`employer_id`) REFERENCES `user`(`id`) ON DELETE CASCADE,
                UNIQUE KEY `uniq_employer_title` (`employer_id`, `title`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # ایندکس‌ها
        indexes = [
            ('user', 'idx_telegram_id', 'telegram_id'),
            ('user', 'idx_email', 'email'),
            ('user', 'idx_role', 'role'),
            ('project', 'idx_status', 'status'),
            ('user_skill', 'idx_skill_id', 'skill_id'),
        ]
        for table, name, col in indexes:
            if not index_exists(cur, table, name):
                cur.execute(f"CREATE INDEX {name} ON `{table}`(`{col}`)")

        conn.commit()
        cur.close()
        conn.close()
        print("✅ Tables and indexes created successfully.")
    except Error as e:
        print(f"❌ Error creating tables: {e}")
        raise

# ================================
# تابع اضافه کردن ستون‌های جدید
# ================================

# ================================
# اجرای اسکریپت
# ================================
if __name__ == "__main__":
    create_database()
    create_tables()

