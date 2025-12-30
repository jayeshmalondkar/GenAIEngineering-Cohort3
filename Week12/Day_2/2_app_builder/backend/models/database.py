from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Text, Date, Boolean, JSON, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP)

    tasks_created = relationship("Task", back_populates="creator", foreign_keys='Task.created_by')
    tasks_assigned = relationship("Task", back_populates="assignee", foreign_keys='Task.assigned_to')
    notifications = relationship("Notification", back_populates="user")
    reports = relationship("Report", back_populates="user")

class Team(Base):
    __tablename__ = 'teams'
    team_id = Column(Integer, primary_key=True)
    team_name = Column(String(255), unique=True, nullable=False)

class TeamMember(Base):
    __tablename__ = 'team_members'
    team_member_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    team_id = Column(Integer, ForeignKey('teams.team_id', ondelete='CASCADE'), nullable=False)

class Task(Base):
    __tablename__ = 'tasks'
    task_id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), nullable=False)
    priority = Column(Integer, nullable=False)
    due_date = Column(Date)
    created_by = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    assigned_to = Column(Integer, ForeignKey('users.user_id'))
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)

    creator = relationship("User", back_populates="tasks_created", foreign_keys=[created_by])
    assignee = relationship("User", back_populates="tasks_assigned", foreign_keys=[assigned_to])
    progress = relationship("TaskProgress", back_populates="task")

class TaskProgress(Base):
    __tablename__ = 'task_progress'
    progress_id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('tasks.task_id', ondelete='CASCADE'), nullable=False)
    progress_status = Column(String(50), nullable=False)
    updated_at = Column(TIMESTAMP)

    task = relationship("Task", back_populates="progress")

class Notification(Base):
    __tablename__ = 'notifications'
    notification_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    message = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP)
    is_read = Column(Boolean, default=False)

    user = relationship("User", back_populates="notifications")

class Report(Base):
    __tablename__ = 'reports'
    report_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    report_data = Column(JSON, nullable=False)
    created_at = Column(TIMESTAMP)

    user = relationship("User", back_populates="reports")