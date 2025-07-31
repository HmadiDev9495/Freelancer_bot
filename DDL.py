from mysql.connector import connect, Error
from CONFIG import Config

def create_tables():
    conn = None
    cur = None
    try:
        conn = connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            port=Config.DB_PORT
        )
        cur = conn.cursor()
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        )
        conn.database = Config.DB_NAME

        cur.execute("""
        CREATE TABLE IF NOT EXISTS `user` (
          `id` INT AUTO_INCREMENT PRIMARY KEY,
          `telegram_id` BIGINT NOT NULL,
          `name` VARCHAR(100) NOT NULL,
          `email` VARCHAR(100) UNIQUE NOT NULL,
          `password_hash` VARCHAR(255) NOT NULL,
          `role` ENUM('freelancer','employer') NOT NULL,
          `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB;
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS `skill` (
          `id` INT AUTO_INCREMENT PRIMARY KEY,
          `name` VARCHAR(100) UNIQUE NOT NULL,
          `category` VARCHAR(100) NOT NULL
        ) ENGINE=InnoDB;
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS `user_skill` (
          `user_id` INT NOT NULL,
          `skill_id` INT NOT NULL,
          `proficiency` TINYINT UNSIGNED DEFAULT 1,
          PRIMARY KEY (`user_id`,`skill_id`),
          FOREIGN KEY (`user_id`) REFERENCES `user`(`id`) ON DELETE CASCADE,
          FOREIGN KEY (`skill_id`) REFERENCES `skill`(`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS `project` (
          `id` INT AUTO_INCREMENT PRIMARY KEY,
          `employer_id` INT NOT NULL,
          `title` VARCHAR(255) NOT NULL,
          `description` TEXT,
          `category` VARCHAR(100) DEFAULT NULL,
          `role` ENUM('freelancer','employer') DEFAULT NULL,
          `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (`employer_id`) REFERENCES `user`(`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """)

        conn.commit()
        print("[DDL] Tables ensured (no reset).")

    except Error as e:
        print(f"[DDL] Error ensuring tables: {e}")
    finally:
        if cur: cur.close()
        if conn and conn.is_connected(): conn.close()

if __name__ == '__main__':
    create_tables()
