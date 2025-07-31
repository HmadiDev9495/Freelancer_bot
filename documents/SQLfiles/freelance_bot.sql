CREATE DATABASE IF NOT EXISTS freelance_bot;
USE freelance_bot;

CREATE TABLE IF NOT EXISTS user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL COMMENT 'Should store bcrypt or Argon2 hashes with salt',
    role ENUM('freelancer', 'employer') NOT NULL,
    rating DECIMAL(3,2) DEFAULT NULL,
    profile_picture VARCHAR(255),
    bio TEXT,
    hourly_rate DECIMAL(10,2),
    login_attempts TINYINT DEFAULT 0,
    last_failed_login DATETIME,
    account_locked BOOLEAN DEFAULT FALSE,
    password_changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    password_expiry_date DATETIME DEFAULT DATE_ADD(CURRENT_TIMESTAMP, INTERVAL 90 DAY),
    two_factor_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    INDEX idx_user_email (email),
    INDEX idx_user_account_status (account_locked),
    INDEX idx_user_telegram_id (telegram_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS auth_token (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token VARCHAR(255) NOT NULL,
    expires_at DATETIME NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    device_info TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    INDEX idx_auth_token_user (user_id),
    INDEX idx_auth_token_token (token)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS skill (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    category ENUM('programming', 'design', 'marketing', 'writing', 'other') NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS user_skill (
    user_id INT NOT NULL,
    skill_id INT NOT NULL,
    proficiency ENUM('beginner', 'intermediate', 'expert') DEFAULT 'intermediate',
    PRIMARY KEY (user_id, skill_id),
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skill(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS project (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    description TEXT,
    budget DECIMAL(10,2),
    status ENUM('draft','open','in_progress','completed', 'disputed') DEFAULT 'draft',
    deadline DATE,
    employer_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (employer_id) REFERENCES user(id),
    INDEX idx_project_status (status),
    INDEX idx_project_employer (employer_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS bid (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    freelancer_id INT NOT NULL,
    amount DECIMAL(10,2),
    days_to_complete INT,
    proposal TEXT,
    status ENUM('pending','accepted','rejected', 'withdrawn') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE,
    FOREIGN KEY (freelancer_id) REFERENCES user(id),
    INDEX idx_bid_project (project_id),
    INDEX idx_bid_freelancer (freelancer_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS task (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    assigned_to INT,
    title VARCHAR(100),
    description TEXT,
    status ENUM('todo', 'in_progress', 'done', 'approved') DEFAULT 'todo',
    due_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to) REFERENCES user(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS project_delivery (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    freelancer_id INT NOT NULL,
    delivery_message TEXT,
    delivery_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status ENUM('submitted', 'approved', 'revision_requested') DEFAULT 'submitted',
    encryption_iv VARBINARY(255) COMMENT 'IV for encrypted data',
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE,
    FOREIGN KEY (freelancer_id) REFERENCES user(id),
    INDEX idx_delivery_project (project_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS delivery_file (
    id INT AUTO_INCREMENT PRIMARY KEY,
    delivery_id INT NOT NULL,
    file_url VARCHAR(255) NOT NULL,
    file_name VARCHAR(100) NOT NULL,
    file_type VARCHAR(50),
    file_size INT,
    file_hash VARCHAR(64) COMMENT 'SHA-256 hash of file content',
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (delivery_id) REFERENCES project_delivery(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS message (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT NOT NULL,
    receiver_id INT NOT NULL,
    project_id INT,
    content TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    encrypted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES user(id),
    FOREIGN KEY (receiver_id) REFERENCES user(id),
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE SET NULL,
    INDEX idx_message_sender (sender_id),
    INDEX idx_message_receiver (receiver_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS message_file (
    id INT AUTO_INCREMENT PRIMARY KEY,
    message_id INT NOT NULL,
    file_url VARCHAR(255) NOT NULL,
    file_name VARCHAR(100) NOT NULL,
    file_type VARCHAR(50),
    file_size INT,
    file_hash VARCHAR(64) COMMENT 'SHA-256 hash of file content',
    FOREIGN KEY (message_id) REFERENCES message(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS payment (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    employer_id INT NOT NULL,
    freelancer_id INT NOT NULL,
    encrypted_amount VARBINARY(255) NOT NULL COMMENT 'Encrypted amount value',
    fee DECIMAL(10,2) NOT NULL,
    payment_method ENUM('credit_card', 'wallet', 'bank_transfer') NOT NULL,
    transaction_id VARCHAR(100) UNIQUE,
    status ENUM('pending', 'completed', 'failed', 'refunded') DEFAULT 'pending',
    payment_date TIMESTAMP NULL,
    encryption_iv VARBINARY(255) COMMENT 'IV for encrypted data',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES project(id),
    FOREIGN KEY (employer_id) REFERENCES user(id),
    FOREIGN KEY (freelancer_id) REFERENCES user(id),
    INDEX idx_payment_project (project_id),
    INDEX idx_payment_status (status)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS wallet (
    user_id INT PRIMARY KEY,
    balance DECIMAL(10,2) DEFAULT 0.00,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS wallet_transaction (
    id INT AUTO_INCREMENT PRIMARY KEY,
    wallet_id INT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    transaction_type ENUM('deposit', 'withdrawal', 'payment', 'refund') NOT NULL,
    reference_id VARCHAR(100),
    description TEXT,
    ip_address VARCHAR(45),
    device_info TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wallet_id) REFERENCES wallet(user_id) ON DELETE CASCADE,
    INDEX idx_wallet_transaction (wallet_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS notification (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    notification_type ENUM(
        'system', 
        'message', 
        'bid', 
        'project_update',
        'payment',
        'delivery',
        'security'
    ) NOT NULL,
    related_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    INDEX idx_notification_user (user_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(50) NOT NULL,
    table_name VARCHAR(50) NOT NULL,
    record_id INT,
    old_values JSON,
    new_values JSON,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_log_user (user_id),
    INDEX idx_audit_log_action (action),
    INDEX idx_audit_log_created (created_at)
) ENGINE=InnoDB;

CREATE USER IF NOT EXISTS 'freelance_app'@'localhost' IDENTIFIED BY 'Strong!Secure@Password123';
GRANT SELECT, INSERT, UPDATE ON freelance_bot.* TO 'freelance_app'@'localhost';

DELIMITER //
CREATE TRIGGER log_user_changes
AFTER UPDATE ON user
FOR EACH ROW
BEGIN
    IF OLD.password_hash != NEW.password_hash THEN
        INSERT INTO audit_log (user_id, action, table_name, record_id, old_values, new_values)
        VALUES (NEW.id, 'PASSWORD_CHANGE', 'user', NEW.id, 
                JSON_OBJECT('old_password_hash', '*****'), 
                JSON_OBJECT('new_password_hash', '*****'));
    END IF;
    
    IF OLD.account_locked != NEW.account_locked THEN
        INSERT INTO audit_log (user_id, action, table_name, record_id, old_values, new_values)
        VALUES (NEW.id, 'ACCOUNT_LOCK_CHANGE', 'user', NEW.id, 
                JSON_OBJECT('old_account_locked', OLD.account_locked), 
                JSON_OBJECT('new_account_locked', NEW.account_locked));
    END IF;
END//
DELIMITER ;

DELIMITER //
CREATE TRIGGER log_payment_changes
AFTER UPDATE ON payment
FOR EACH ROW
BEGIN
    IF OLD.status != NEW.status THEN
        INSERT INTO audit_log (user_id, action, table_name, record_id, old_values, new_values)
        VALUES (NEW.employer_id, 'PAYMENT_STATUS_CHANGE', 'payment', NEW.id, 
                JSON_OBJECT('old_status', OLD.status, 'amount', OLD.encrypted_amount), 
                JSON_OBJECT('new_status', NEW.status, 'amount', NEW.encrypted_amount));
    END IF;
END//
DELIMITER ;