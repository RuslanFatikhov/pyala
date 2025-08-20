import sys
from pathlib import Path

# Добавляем корневую директорию проекта в python3 path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Импортируем приложение Flask
from app import app as application

if __name__ == "__main__":
    application.run()