import smtplib
import requests
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List

class NotificationService:
    """Сервис уведомлений"""
    
    def __init__(self):
        self.smtp_host = os.getenv('EMAIL_SMTP_HOST')
        self.smtp_port = int(os.getenv('EMAIL_SMTP_PORT', 587))
        self.email_user = os.getenv('EMAIL_USER')
        self.email_pass = os.getenv('EMAIL_PASS')
        self.email_to = os.getenv('EMAIL_TO')
        self.telegram_webhook = os.getenv('TELEGRAM_WEBHOOK_URL')
        self.currency = os.getenv('CURRENCY', 'RUB')
    
    def send_order_notification(self, order_id: int, form_data: Dict, cart_items: List[Dict]):
        """Отправка уведомлений о новом заказе"""
        # Email уведомление
        if self._is_email_configured():
            try:
                self._send_email_notification(order_id, form_data, cart_items)
            except Exception as e:
                logging.error(f"Error sending email notification: {e}")
        
        # Telegram уведомление
        if self.telegram_webhook:
            try:
                self._send_telegram_notification(order_id, form_data, cart_items)
            except Exception as e:
                logging.error(f"Error sending telegram notification: {e}")
    
    def _is_email_configured(self) -> bool:
        """Проверка настройки email"""
        return all([self.smtp_host, self.email_user, self.email_pass, self.email_to])
    
    def _send_email_notification(self, order_id: int, form_data: Dict, cart_items: List[Dict]):
        """Отправка email уведомления"""
        # Подсчет общей суммы
        total = sum(item['total'] for item in cart_items)
        
        # Формирование содержимого письма
        subject = f"Новый заказ #{order_id}"
        
        body = f"""
Получен новый заказ #{order_id}

Данные покупателя:
- Имя: {form_data['name']}
- Телефон: {form_data['phone']}
- Город: {form_data['city']}
- Адрес: {form_data['address']}
- Комментарий: {form_data.get('comment', 'Нет')}

Товары:
"""
        
        for item in cart_items:
            product = item['product']
            body += f"- {product['title']} x{item['qty']} = {item['total']} {self.currency}\n"
        
        body += f"\nИтого: {total} {self.currency}"
        
        # Отправка письма
        msg = MIMEMultipart()
        msg['From'] = self.email_user
        msg['To'] = self.email_to
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.email_user, self.email_pass)
            server.send_message(msg)
    
    def _send_telegram_notification(self, order_id: int, form_data: Dict, cart_items: List[Dict]):
        """Отправка Telegram уведомления"""
        total = sum(item['total'] for item in cart_items)
        
        message = f"🆕 Новый заказ #{order_id}\n\n"
        message += f"👤 {form_data['name']}\n"
        message += f"📱 {form_data['phone']}\n"
        message += f"🏙 {form_data['city']}\n"
        message += f"📍 {form_data['address']}\n\n"
        
        message += "🛍 Товары:\n"
        for item in cart_items:
            product = item['product']
            message += f"• {product['title']} x{item['qty']} = {item['total']} {self.currency}\n"
        
        message += f"\n💰 Итого: {total} {self.currency}"
        
        if form_data.get('comment'):
            message += f"\n💬 {form_data['comment']}"
        
        payload = {'text': message}
        requests.post(self.telegram_webhook, json=payload, timeout=10)