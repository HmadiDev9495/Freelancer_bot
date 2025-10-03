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
  `phone` VARCHAR(20) DEFAULT NULL,
  `linkedin` VARCHAR(255) DEFAULT NULL,
  `github` VARCHAR(255) DEFAULT NULL,
  `website` VARCHAR(255) DEFAULT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `last_login` DATETIME DEFAULT NULL,
  INDEX (`telegram_id`),
  INDEX (`email`),
  INDEX (`role`)
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

CREATE TABLE IF NOT EXISTS `project` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `employer_id` INT NOT NULL,
  `title` VARCHAR(255) NOT NULL,
  `description` TEXT,
  `category` VARCHAR(100) DEFAULT NULL,
  `role` ENUM('freelancer','employer') DEFAULT NULL,
  `budget` DECIMAL(12,2) DEFAULT NULL,
  `delivery_days` INT DEFAULT NULL,
  `status` ENUM('draft','open','in_progress','done','cancelled') NOT NULL DEFAULT 'draft',
  `progress` TINYINT UNSIGNED DEFAULT 0,
  `updated_at` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  FOREIGN KEY (`employer_id`) REFERENCES `user`(`id`) ON DELETE CASCADE,
  UNIQUE KEY `uniq_employer_title` (`employer_id`,`title`)
) ENGINE=InnoDB;
ALTER TABLE `project` ADD COLUMN `budget` DECIMAL(10,2) NULL AFTER `role`;
ALTER TABLE `project` ADD COLUMN `status`
  ENUM('draft','open','in_progress','done','cancelled')
  NOT NULL DEFAULT 'draft';
ALTER TABLE `project` ADD COLUMN `progress` TINYINT UNSIGNED DEFAULT 0;
ALTER TABLE `project` ADD COLUMN `updated_at` TIMESTAMP NULL DEFAULT NULL
  ON UPDATE CURRENT_TIMESTAMP;
