-- ===========================
-- SCHEMA FULL – 2025-08-12
-- دیتابیس کامل از صفر، هم‌راستا با کد ربات
-- ===========================

-- USER
CREATE TABLE IF NOT EXISTS `user` (
  `id`             INT AUTO_INCREMENT PRIMARY KEY,
  `telegram_id`    BIGINT        NOT NULL,
  `name`           VARCHAR(100)  NOT NULL,
  `email`          VARCHAR(100)  NOT NULL,
  `password_hash`  VARCHAR(255)  NOT NULL,
  `role`           ENUM('employer','freelancer') NOT NULL,
  `rating`         DECIMAL(3,2)  NULL,
  `profile_picture` VARCHAR(255) NULL,
  `bio`            TEXT          NULL,
  `hourly_rate`    DECIMAL(10,2) NULL,
  `phone`          VARCHAR(20)   NULL,
  `linkedin`       VARCHAR(255)  NULL,
  `github`         VARCHAR(255)  NULL,
  `website`        VARCHAR(255)  NULL,
  `created_at`     TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP,
  `last_login`     DATETIME      NULL,
  UNIQUE KEY `uq_user_email` (`email`),
  INDEX `idx_user_telegram_id` (`telegram_id`),
  INDEX `idx_user_role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- SKILL
CREATE TABLE IF NOT EXISTS `skill` (
  `id`       INT AUTO_INCREMENT PRIMARY KEY,
  `name`     VARCHAR(100) NOT NULL,
  `category` VARCHAR(100) NOT NULL,
  UNIQUE KEY `uq_skill_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- USER_SKILL (many-to-many)
CREATE TABLE IF NOT EXISTS `user_skill` (
  `user_id`     INT NOT NULL,
  `skill_id`    INT NOT NULL,
  `proficiency` TINYINT UNSIGNED DEFAULT 1,
  PRIMARY KEY (`user_id`,`skill_id`),
  CONSTRAINT `fk_user_skill_user`
    FOREIGN KEY (`user_id`) REFERENCES `user`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_user_skill_skill`
    FOREIGN KEY (`skill_id`) REFERENCES `skill`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- PROJECT
CREATE TABLE IF NOT EXISTS `project` (
  `id`           INT AUTO_INCREMENT PRIMARY KEY,
  `employer_id`  INT           NOT NULL,
  `title`        VARCHAR(255)  NOT NULL,
  `description`  TEXT          NULL,
  `category`     VARCHAR(100)  NULL,
  `role`         VARCHAR(100)  NULL,
  `budget`       DECIMAL(12,2) NULL,
  `delivery_days` INT          NULL,
  `created_at`   TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_project_user`
    FOREIGN KEY (`employer_id`) REFERENCES `user`(`id`) ON DELETE CASCADE,
  UNIQUE KEY `uniq_employer_title` (`employer_id`, `title`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
