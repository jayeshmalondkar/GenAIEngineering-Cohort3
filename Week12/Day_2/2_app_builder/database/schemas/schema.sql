-- schema.sql: PostgreSQL schema for managing a task management system.

CREATE TABLE Users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Teams (
    team_id SERIAL PRIMARY KEY,
    team_name VARCHAR(255) UNIQUE NOT NULL
);

CREATE TABLE TeamMembers (
    team_member_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    team_id INT NOT NULL REFERENCES Teams(team_id) ON DELETE CASCADE
);

CREATE TABLE Tasks (
    task_id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL,
    priority SMALLINT NOT NULL,
    due_date DATE,
    created_by INT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    assigned_to INT REFERENCES Users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE TaskProgress (
    progress_id SERIAL PRIMARY KEY,
    task_id INT NOT NULL REFERENCES Tasks(task_id) ON DELETE CASCADE,
    progress_status VARCHAR(50) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Notifications (
    notification_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    message VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT FALSE
);

CREATE TABLE Reports (
    report_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    report_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_users_username ON Users(username);
CREATE INDEX idx_users_email ON Users(email);
CREATE INDEX idx_teams_team_name ON Teams(team_name);
CREATE INDEX idx_tasks_title ON Tasks(title);
CREATE INDEX idx_tasks_status ON Tasks(status);
CREATE INDEX idx_tasks_priority ON Tasks(priority);
CREATE INDEX idx_tasks_due_date ON Tasks(due_date);
CREATE INDEX idx_notifications_user_id ON Notifications(user_id);
CREATE INDEX idx_notifications_created_at ON Notifications(created_at);
CREATE INDEX idx_notifications_is_read ON Notifications(is_read);
CREATE INDEX idx_reports_created_at ON Reports(created_at);