-- seed_data.sql: Seed data for testing task management system.

INSERT INTO Users (username, email, password_hash) VALUES
('john_doe', 'john@example.com', 'hashedpassword1'),
('jane_smith', 'jane@example.com', 'hashedpassword2');

INSERT INTO Teams (team_name) VALUES
('Development'),
('Marketing');

INSERT INTO Tasks (title, status, priority, created_by, assigned_to) VALUES
('Implement Login', 'To Do', 2, 1, 2),
('Design Banner', 'In Progress', 1, 2, 1);