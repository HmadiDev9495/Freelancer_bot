-- SQL schema for freelance_bot database
CREATE TABLE IF NOT EXISTS `user` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `telegram_id` BIGINT UNIQUE NOT NULL,
  `name` VARCHAR(100) NOT NULL,
  `email` VARCHAR(100) UNIQUE NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `role` ENUM('employer','freelancer') NOT NULL,
  `rating` DECIMAL(3,2) DEFAULT NULL,
  `profile_picture` VARCHAR(255) DEFAULT NULL,
  `bio` TEXT DEFAULT NULL,
  `hourly_rate` DECIMAL(10,2) DEFAULT NULL,
  `login_attempts` TINYINT DEFAULT 0,
  `last_failed_login` DATETIME DEFAULT NULL,
  `account_locked` BOOLEAN DEFAULT FALSE,
  `password_changed_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `password_expiry_date` DATETIME DEFAULT NULL,
  `two_factor_enabled` BOOLEAN DEFAULT FALSE,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `last_login` DATETIME DEFAULT NULL,
  INDEX (`telegram_id`),
  INDEX (`email`),
  INDEX (`account_locked`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `skill` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(100) UNIQUE NOT NULL,
  `category` VARCHAR(100) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `user_skill` (
  `user_id` INT NOT NULL,
  `skill_id` INT NOT NULL,
  `proficiency` TINYINT UNSIGNED DEFAULT 1,
  PRIMARY KEY (`user_id`,`skill_id`),
  FOREIGN KEY (`user_id`) REFERENCES `user`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`skill_id`) REFERENCES `skill`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

