
ALTER TABLE `user`
  ADD COLUMN IF NOT EXISTS `rating`          DECIMAL(3,2)   NULL,
  ADD COLUMN IF NOT EXISTS `profile_picture` VARCHAR(255)   NULL,
  ADD COLUMN IF NOT EXISTS `bio`             TEXT           NULL,
  ADD COLUMN IF NOT EXISTS `hourly_rate`     DECIMAL(10,2)  NULL,
  ADD COLUMN IF NOT EXISTS `phone`           VARCHAR(20)    NULL,
  ADD COLUMN IF NOT EXISTS `linkedin`        VARCHAR(255)   NULL,
  ADD COLUMN IF NOT EXISTS `github`          VARCHAR(255)   NULL,
  ADD COLUMN IF NOT EXISTS `website`         VARCHAR(255)   NULL,
  ADD COLUMN IF NOT EXISTS `created_at`      TIMESTAMP      NULL DEFAULT CURRENT_TIMESTAMP,
  ADD COLUMN IF NOT EXISTS `last_login`      DATETIME       NULL;

DROP INDEX `telegram_id` ON `user`;
DROP INDEX `uq_user_telegram_id` ON `user`;


CREATE INDEX IF NOT EXISTS `idx_user_telegram_id` ON `user`(`telegram_id`);

ALTER TABLE `skill`
  ADD UNIQUE KEY `uq_skill_name` (`name`);


ALTER TABLE `user_skill`
  ADD PRIMARY KEY (`user_id`,`skill_id`);


CREATE TABLE IF NOT EXISTS `project` (
  `id`           INT AUTO_INCREMENT PRIMARY KEY,
  `employer_id`  INT          NOT NULL,
  `title`        VARCHAR(255) NOT NULL,
  `description`  TEXT         NULL,
  `category`     VARCHAR(100) NULL,
  `role`         VARCHAR(100) NULL,
  `budget`       DECIMAL(12,2)    NULL,
  `delivery_days` INT             NULL,
  `created_at`   TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_project_user`
    FOREIGN KEY (`employer_id`) REFERENCES `user`(`id`) ON DELETE CASCADE,
  UNIQUE KEY `uniq_employer_title` (`employer_id`, `title`)
) ENGINE=InnoDB;

ALTER TABLE `project`
  ADD COLUMN IF NOT EXISTS `status` ENUM('draft','open','in_progress','done','cancelled') NOT NULL DEFAULT 'open',
  ADD COLUMN IF NOT EXISTS `progress` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS `updated_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;