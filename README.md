# Freelancer_bot
## 📚 مستندات دیتابیس

### ERD (Mermaid)
```mermaid
erDiagram
    user ||--o{ user_skill : has
    skill ||--o{ user_skill : used_by
    user ||--o{ project : posts

    user {
        INT id PK
        BIGINT telegram_id
        VARCHAR name
        VARCHAR email
        VARCHAR password_hash
        ENUM role
        DECIMAL rating
        VARCHAR profile_picture
        TEXT bio
        DECIMAL hourly_rate
        VARCHAR phone
        VARCHAR linkedin
        VARCHAR github
        VARCHAR website
        TIMESTAMP created_at
        DATETIME last_login
    }

    skill {
        INT id PK
        VARCHAR name
        VARCHAR category
    }

    user_skill {
        INT user_id FK
        INT skill_id FK
        TINYINT proficiency
    }

    project {
        INT id PK
        INT employer_id FK
        VARCHAR title
        TEXT description
        VARCHAR category
        VARCHAR role
        DECIMAL budget
        INT delivery_days
        TIMESTAMP created_at
    }
