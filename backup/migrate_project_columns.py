from mysql.connector import connect, Error
from CONFIG import Config

SQLS = [
    "ALTER TABLE `project` ADD COLUMN `budget` DECIMAL(10,2) NULL",
    "ALTER TABLE `project` ADD COLUMN `status` ENUM('draft','open','in_progress','done','cancelled') NOT NULL DEFAULT 'draft'",
    "ALTER TABLE `project` ADD COLUMN `progress` TINYINT UNSIGNED DEFAULT 0",
    "ALTER TABLE `project` ADD COLUMN `updated_at` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP",
]

def main():
    try:
        conn = connect(
            host=Config.DB_HOST, port=Config.DB_PORT,
            user=Config.DB_USER, password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        cur = conn.cursor()
        for q in SQLS:
            try:
                cur.execute(q)
                conn.commit()
                print("[OK]", q)
            except Error as e:
                s = str(e)
                if "Duplicate column" in s:
                    print("[SKIP - already exists]", q)
                elif "doesn't exist" in s and "project" in s:
                    print("[ERR] Table `project` وجود ندارد. ابتدا freelance_bot.sql را ایمپورت کن.")
                    return
                else:
                    print("[ERR]", s)
        cur.execute("SHOW COLUMNS FROM `project`")
        print("Columns:", [r[0] for r in cur.fetchall()])
    finally:
        try: cur.close(); conn.close()
        except: pass

if __name__ == "__main__":
    main()
