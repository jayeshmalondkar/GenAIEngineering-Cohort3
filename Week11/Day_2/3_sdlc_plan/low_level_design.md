# Low-Level Design Document for News Aggregator App

## 1. Overview
The News Aggregator App is designed to aggregate articles from various news sources while supporting user authentication, article retrieval, and caching strategies. This document outlines the low-level design, detailing module structures, class diagrams, database schemas, route implementations, service layers, and other crucial components to guide implementation.

---

## 2. Module and Package Structure
The following is the proposed package structure for the application:

```
news_aggregator/
│
├── app/
│   ├── main.py                # Entry point for FastAPI application
│   ├── api/
│   │   ├── v1/
│   │   │   ├── routers/       # Route handlers
│   │   │   └── models.py      # Pydantic models for request and response
│   │   ├── dependencies/       # Dependency injection functions
│   │   └── exceptions.py       # Custom exceptions
│   ├── db/
│   │   ├── models/            # SQLAlchemy models
│   │   ├── repositories/       # Repository pattern implementations
│   │   └── schemas.py         # Database schema definitions
│   ├── services/              # Business logic implementations
│   ├── tests/                 # Unit tests and mocks
│   ├── cache/                 # Caching logic with Redis
│   ├── celery_jobs/           # Celery task definitions
│   └── config.py              # Configuration management
│
└── frontend/
    ├── streamlit_app.py       # Streamlit frontend implementation
    └── components/             # Reusable Streamlit components
```

---

## 3. Class Diagrams

### 3.1 User Management
```classdiagram
class User:
    + id: int
    + username: str
    + email: str
    + hashed_password: str
    + __init__(username: str, email: str, hashed_password: str)
    + verify_password(password: str) -> bool
```

### 3.2 Article Management
```classdiagram
class Article:
    + id: int
    + title: str
    + content: str
    + source: str
    + published_at: datetime
    + __init__(title: str, content: str, source: str, published_at: datetime)
    + fetch_external_article(source: str) -> Article
```

### 3.3 Services
```classdiagram
class ArticleService:
    + get_articles(user_id: int) -> List[Article]
    + search_articles(query: str) -> List[Article]
```

---

## 4. Database Table Schemas
### 4.1 User Table
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4.2 Article Table
```sql
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    source VARCHAR(255) NOT NULL,
    published_at TIMESTAMP,
    user_id INT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
-- Indexes
CREATE INDEX idx_article_source ON articles(source);
CREATE INDEX idx_article_title ON articles(title);
```

---

## 5. FastAPI Route Implementations
### 5.1 Authentication Route
```python
from fastapi import APIRouter, Depends
from .dependencies import get_current_user
from .models import User
from .services import AuthService

router = APIRouter()

@router.post("/auth/login")
async def login(user: User):
    return await AuthService.authenticate(user)
```

### 5.2 Article Retrieval Route
```python
@router.get("/articles")
async def get_articles(current_user: User = Depends(get_current_user)):
    return ArticleService.get_articles(current_user.id)
```

---

## 6. Streamlit Page Layouts and Components
### 6.1 Streamlit Main Page
```python
import streamlit as st

def main():
    st.title("News Aggregator")
    if st.button("Fetch Articles"):
        articles = fetch_articles()  # function to fetch articles from the backend
        for article in articles:
            st.subheader(article.title)
            st.write(article.content)

if __name__ == "__main__":
    main()
```

### 6.2 Components Structure
- `ArticleDisplay`: Displays a single article.
- `AuthForm`: Handles user authentication input.

---

## 7. Data Models and Pydantic Schemas
### 7.1 User Schema
```python
from pydantic import BaseModel

class UserSchema(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        orm_mode = True
```

### 7.2 Article Schema
```python
class ArticleSchema(BaseModel):
    id: int
    title: str
    content: str
    source: str
    published_at: datetime

    class Config:
        orm_mode = True
```

---

## 8. Service Layer Design Patterns
- **Service Layer**: Encapsulates business logic; e.g., `ArticleService` for article-related operations.
- **Dependency Injection**: Used to inject services into API routes for better testability and separation of concerns.

---

## 9. Repository Pattern Implementations
### 9.1 Article Repository
```python
from sqlalchemy.orm import Session
from .models import Article

class ArticleRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_articles_by_user(self, user_id: int):
        return self.db.query(Article).filter(Article.user_id == user_id).all()
```

---

## 10. Unit Testing Structure and Mocking Strategies
### 10.1 Tests Structure
```
tests/
├── test_auth.py
├── test_articles.py
└── conftest.py  # Shared fixtures
```

### 10.2 Mocking Strategies
- Use `unittest.mock` to mock external calls (e.g., to Redis, external APIs).
- Dependency Overriding in FastAPI for unit tests.

```python
from fastapi.testclient import TestClient

client = TestClient(app)

def test_get_articles():
    response = client.get("/articles", headers={"Authorization": "Bearer fake_token"})
    assert response.status_code == 200
```

---

## 11. Code Organization and Folder Structure
- Group related functionalities together (e.g., routes, services, models).
- Use folders for modules, organizing files logically according to functionality.

---

## 12. Configuration Management Approach
### 12.1 Configuration File
Use environment variables and a configuration file (`config.py`) to manage settings for databases, cache, and third-party integrations. This allows flexible deployment configurations and local development setups.

```python
import os

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
```

### 12.2 Settings Management
Utilize `.env` files for local development with `python-dotenv` and container orchestration tools for production configurations.

---

This design document aims to create a scalable, maintainable, and robust architecture to meet both functional requirements (aggregation of news articles) and non-functional requirements (performance, security, and extensibility) necessary for the News Aggregator App.