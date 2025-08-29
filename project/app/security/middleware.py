# app/security/middleware.py
from functools import wraps
from flask import request, session, redirect, url_for, abort, current_app
from datetime import datetime, timedelta
import os
import logging
from typing import Dict

class SecurityMiddleware:
    """Middleware для обеспечения безопасности приложения"""
    
    def __init__(self):
        self.failed_attempts: Dict[str, list] = {}
        self.locked_ips: Dict[str, datetime] = {}
        self.max_attempts = int(os.getenv('MAX_LOGIN_ATTEMPTS', 5))
        self.lockout_minutes = int(os.getenv('LOGIN_LOCKOUT_MINUTES', 30))
    
    def is_ip_locked(self, ip: str) -> bool:
        """Проверка блокировки IP"""
        if ip in self.locked_ips:
            lock_time = self.locked_ips[ip]
            if datetime.now() - lock_time < timedelta(minutes=self.lockout_minutes):
                return True
            else:
                # Разблокируем IP если время истекло
                del self.locked_ips[ip]
                if ip in self.failed_attempts:
                    del self.failed_attempts[ip]
        return False
    
    def record_failed_login(self, ip: str):
        """Запись неудачной попытки входа"""
        now = datetime.now()
        
        if ip not in self.failed_attempts:
            self.failed_attempts[ip] = []
        
        # Добавляем текущую попытку
        self.failed_attempts[ip].append(now)
        
        # Убираем попытки старше часа
        self.failed_attempts[ip] = [
            attempt for attempt in self.failed_attempts[ip]
            if now - attempt < timedelta(hours=1)
        ]
        
        # Блокируем IP если превышен лимит
        if len(self.failed_attempts[ip]) >= self.max_attempts:
            self.locked_ips[ip] = now
            logging.warning(f"IP {ip} заблокирован за превышение лимита попыток входа")
    
    def record_successful_login(self, ip: str):
        """Запись успешного входа"""
        # Очищаем неудачные попытки при успешном входе
        if ip in self.failed_attempts:
            del self.failed_attempts[ip]
        if ip in self.locked_ips:
            del self.locked_ips[ip]

# Создаем глобальный экземпляр
security_middleware = SecurityMiddleware()


def admin_required(f):
    """Декоратор для проверки авторизации админа с дополнительной безопасностью"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        
        # Проверка блокировки IP
        if security_middleware.is_ip_locked(client_ip):
            logging.warning(f"Заблокированный IP {client_ip} пытается получить доступ к админке")
            abort(429)  # Too Many Requests
        
        # Проверка сессии администратора
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login'))
        
        # Проверка времени сессии
        session_start = session.get('session_start')
        if session_start:
            session_duration = datetime.now() - datetime.fromisoformat(session_start)
            max_duration = timedelta(minutes=int(os.getenv('SESSION_TIMEOUT_MINUTES', 60)))
            
            if session_duration > max_duration:
                session.clear()
                logging.info(f"Сессия админа истекла для IP {client_ip}")
                return redirect(url_for('admin.login'))
        
        return f(*args, **kwargs)
    return decorated_function


def rate_limit(requests_per_minute: int = 60):
    """Ограничение частоты запросов"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Здесь можно добавить логику rate limiting
            # Для простоты пропускаем реализацию
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# app/security/data_protection.py
import os
import stat
import logging
from pathlib import Path

class DataProtection:
    """Класс для защиты файлов с персональными данными"""
    
    @staticmethod
    def secure_file_permissions(file_path: str):
        """Установка безопасных прав доступа к файлу"""
        try:
            # Права только для владельца (600)
            os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)
            logging.info(f"Установлены безопасные права для файла {file_path}")
        except Exception as e:
            logging.error(f"Ошибка установки прав для файла {file_path}: {e}")
    
    @staticmethod
    def secure_directory_permissions(dir_path: str):
        """Установка безопасных прав доступа к директории"""
        try:
            # Права только для владельца (700)
            os.chmod(dir_path, stat.S_IRWXU)
            logging.info(f"Установлены безопасные права для директории {dir_path}")
        except Exception as e:
            logging.error(f"Ошибка установки прав для директории {dir_path}: {e}")
    
    @staticmethod
    def setup_secure_data_directory():
        """Настройка безопасной директории для данных"""
        data_dir = Path('./data')
        logs_dir = Path('./logs')
        
        # Создаем директории если не существуют
        data_dir.mkdir(exist_ok=True)
        logs_dir.mkdir(exist_ok=True)
        
        # Устанавливаем безопасные права
        DataProtection.secure_directory_permissions(str(data_dir))
        DataProtection.secure_directory_permissions(str(logs_dir))
        
        # Защищаем файлы данных
        orders_file = data_dir / 'orders.csv'
        if orders_file.exists():
            DataProtection.secure_file_permissions(str(orders_file))


# app/security/audit_logger.py
import logging
import os
from datetime import datetime
from flask import request, session

class AuditLogger:
    """Логирование событий безопасности"""
    
    def __init__(self):
        self.setup_logger()
    
    def setup_logger(self):
        """Настройка логгера безопасности"""
        log_dir = './logs'
        os.makedirs(log_dir, exist_ok=True)
        
        # Настраиваем отдельный логгер для безопасности
        self.security_logger = logging.getLogger('security')
        self.security_logger.setLevel(logging.INFO)
        
        # Файловый обработчик
        security_handler = logging.FileHandler('./logs/security.log')
        security_handler.setLevel(logging.INFO)
        
        # Формат логов
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        security_handler.setFormatter(formatter)
        
        self.security_logger.addHandler(security_handler)
        
        # Защищаем файл логов
        from .data_protection import DataProtection
        DataProtection.secure_file_permissions('./logs/security.log')
    
    def log_admin_login(self, username: str, success: bool):
        """Логирование попыток входа в админку"""
        ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        status = "SUCCESS" if success else "FAILED"
        
        self.security_logger.info(
            f"ADMIN_LOGIN - {status} - User: {username} - IP: {ip}"
        )
    
    def log_data_access(self, order_id: int, admin_user: str, action: str):
        """Логирование доступа к персональным данным"""
        ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        
        self.security_logger.info(
            f"DATA_ACCESS - Order: {order_id} - Admin: {admin_user} - Action: {action} - IP: {ip}"
        )
    
    def log_order_creation(self, order_id: int):
        """Логирование создания заказа"""
        ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        
        self.security_logger.info(
            f"ORDER_CREATED - Order: {order_id} - IP: {ip}"
        )
    
    def log_security_event(self, event_type: str, details: str):
        """Логирование событий безопасности"""
        ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        
        self.security_logger.warning(
            f"SECURITY_EVENT - {event_type} - {details} - IP: {ip}"
        )

# Создаем глобальный экземпляр
audit_logger = AuditLogger()