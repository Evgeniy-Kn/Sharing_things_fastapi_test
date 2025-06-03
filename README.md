# 🔄 Sharing_things_api_test

Приложение для обмена товарами между пользователями. Реализовано с использованием **FastAPI**, **SQLAlchemy**, **Pydantic**, **JWT-аутентификации**, и **SQLite**.

---

## 📦 Установка и запуск

### 1. Клонирование репозитория

```git clone https://github.com/Evgeniy-Kn/Sharing_things_fastapi_test.git```

### 2. Переход в директорию Sharing_things_fastapi_test
```cd Sharing_things_fastapi_test```

### 3. Создание виртуального окружения

```python3 -m venv venv```

### 4. Активация виртуального окружения

```source venv/bin/activate``` - для Linux/macOS 

```venv\Scripts\activate.ps1``` - для Windows (PowerShell)

### 5. Установка зависимостей

```pip3 install -r requirements.txt```

### 6. Запуск сервера uvicorn

```uvicorn src.main:app```

### 7. Открыть в браузере Интерактивную документацию по API

```http://127.0.0.1:8000/docs```

---

## 🧪 Запуск тестов

```pytest -v```