CREATE TABLE `user` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `name` varchar(100),
  `email` varchar(100) UNIQUE,
  `password_hash` varchar(255),
  `role` enum(freelancer,employer),
  `rating` decimal(3,2),
  `profile_picture` varchar(255),
  `bio` text,
  `hourly_rate` decimal(10,2),
  `login_attempts` tinyint,
  `last_failed_login` datetime,
  `account_locked` boolean,
  `password_changed_at` datetime,
  `password_expiry_date` datetime,
  `two_factor_enabled` boolean,
  `created_at` timestamp,
  `last_login` datetime
);

CREATE TABLE `auth_token` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `user_id` int,
  `token` varchar(255),
  `expires_at` datetime,
  `is_revoked` boolean,
  `device_info` text,
  `ip_address` varchar(45),
  `created_at` timestamp
);

CREATE TABLE `skill` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `name` varchar(50) UNIQUE,
  `category` enum(programming,design,marketing,writing,other)
);

CREATE TABLE `user_skill` (
  `user_id` int,
  `skill_id` int,
  `proficiency` enum(beginner,intermediate,expert)
);

CREATE TABLE `project` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `title` varchar(100),
  `description` text,
  `budget` decimal(10,2),
  `status` enum(draft,open,in_progress,completed,disputed),
  `deadline` date,
  `employer_id` int,
  `created_at` timestamp,
  `last_updated` timestamp
);

CREATE TABLE `bid` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `project_id` int,
  `freelancer_id` int,
  `amount` decimal(10,2),
  `days_to_complete` int,
  `proposal` text,
  `status` enum(pending,accepted,rejected,withdrawn),
  `created_at` timestamp
);

CREATE TABLE `task` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `project_id` int,
  `assigned_to` int,
  `title` varchar(100),
  `description` text,
  `status` enum(todo,in_progress,done,approved),
  `due_date` date,
  `created_at` timestamp
);

CREATE TABLE `project_delivery` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `project_id` int,
  `freelancer_id` int,
  `delivery_message` text,
  `delivery_date` timestamp,
  `status` enum(submitted,approved,revision_requested),
  `encryption_iv` varbinary(255)
);

CREATE TABLE `delivery_file` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `delivery_id` int,
  `file_url` varchar(255),
  `file_name` varchar(100),
  `file_type` varchar(50),
  `file_size` int,
  `file_hash` varchar(64),
  `uploaded_at` timestamp
);

CREATE TABLE `message` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `sender_id` int,
  `receiver_id` int,
  `project_id` int,
  `content` text,
  `is_read` boolean,
  `encrypted` boolean,
  `created_at` timestamp
);

CREATE TABLE `message_file` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `message_id` int,
  `file_url` varchar(255),
  `file_name` varchar(100),
  `file_type` varchar(50),
  `file_size` int,
  `file_hash` varchar(64)
);

CREATE TABLE `payment` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `project_id` int,
  `employer_id` int,
  `freelancer_id` int,
  `encrypted_amount` varbinary(255),
  `fee` decimal(10,2),
  `payment_method` enum(credit_card,wallet,bank_transfer),
  `transaction_id` varchar(100),
  `status` enum(pending,completed,failed,refunded),
  `payment_date` timestamp,
  `encryption_iv` varbinary(255),
  `created_at` timestamp
);

CREATE TABLE `wallet` (
  `user_id` int PRIMARY KEY,
  `balance` decimal(10,2),
  `last_updated` timestamp
);

CREATE TABLE `wallet_transaction` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `wallet_id` int,
  `amount` decimal(10,2),
  `transaction_type` enum(deposit,withdrawal,payment,refund),
  `reference_id` varchar(100),
  `description` text,
  `ip_address` varchar(45),
  `device_info` text,
  `created_at` timestamp
);

CREATE TABLE `notification` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `user_id` int,
  `title` varchar(100),
  `content` text,
  `is_read` boolean,
  `notification_type` enum(system,message,bid,project_update,payment,delivery,security),
  `related_id` int,
  `created_at` timestamp
);

CREATE TABLE `audit_log` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `user_id` int,
  `action` varchar(50),
  `table_name` varchar(50),
  `record_id` int,
  `old_values` json,
  `new_values` json,
  `ip_address` varchar(45),
  `user_agent` text,
  `created_at` timestamp
);

ALTER TABLE `user_skill` COMMENT = 'Primary key is (user_id, skill_id)';

ALTER TABLE `auth_token` ADD FOREIGN KEY (`user_id`) REFERENCES `user` (`id`);

ALTER TABLE `user_skill` ADD FOREIGN KEY (`user_id`) REFERENCES `user` (`id`);

ALTER TABLE `user_skill` ADD FOREIGN KEY (`skill_id`) REFERENCES `skill` (`id`);

ALTER TABLE `project` ADD FOREIGN KEY (`employer_id`) REFERENCES `user` (`id`);

ALTER TABLE `bid` ADD FOREIGN KEY (`project_id`) REFERENCES `project` (`id`);

ALTER TABLE `bid` ADD FOREIGN KEY (`freelancer_id`) REFERENCES `user` (`id`);

ALTER TABLE `task` ADD FOREIGN KEY (`project_id`) REFERENCES `project` (`id`);

ALTER TABLE `task` ADD FOREIGN KEY (`assigned_to`) REFERENCES `user` (`id`);

ALTER TABLE `project_delivery` ADD FOREIGN KEY (`project_id`) REFERENCES `project` (`id`);

ALTER TABLE `project_delivery` ADD FOREIGN KEY (`freelancer_id`) REFERENCES `user` (`id`);

ALTER TABLE `delivery_file` ADD FOREIGN KEY (`delivery_id`) REFERENCES `project_delivery` (`id`);

ALTER TABLE `message` ADD FOREIGN KEY (`sender_id`) REFERENCES `user` (`id`);

ALTER TABLE `message` ADD FOREIGN KEY (`receiver_id`) REFERENCES `user` (`id`);

ALTER TABLE `message` ADD FOREIGN KEY (`project_id`) REFERENCES `project` (`id`);

ALTER TABLE `message_file` ADD FOREIGN KEY (`message_id`) REFERENCES `message` (`id`);

ALTER TABLE `payment` ADD FOREIGN KEY (`project_id`) REFERENCES `project` (`id`);

ALTER TABLE `payment` ADD FOREIGN KEY (`employer_id`) REFERENCES `user` (`id`);

ALTER TABLE `payment` ADD FOREIGN KEY (`freelancer_id`) REFERENCES `user` (`id`);

ALTER TABLE `wallet` ADD FOREIGN KEY (`user_id`) REFERENCES `user` (`id`);

ALTER TABLE `wallet_transaction` ADD FOREIGN KEY (`wallet_id`) REFERENCES `wallet` (`user_id`);

ALTER TABLE `notification` ADD FOREIGN KEY (`user_id`) REFERENCES `user` (`id`);

ALTER TABLE `audit_log` ADD FOREIGN KEY (`user_id`) REFERENCES `user` (`id`);
