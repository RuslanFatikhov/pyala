### app/__init__.py
from flask import Flask, render_template
from dotenv import load_dotenv
import os

def get_category_url(category):
    """Возвращает URL для категории товара"""
    category_urls = {
        'пиалы': '/pialki',
        'чашки': '/chashki', 
        'чайники': '/chainiki',
        'наборы': '/nabory'
    }
    return category_urls.get(category, '/catalog')


def create_app():
    load_dotenv()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    from .routes_public import public_bp
    from .routes_admin import admin_bp
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Добавьте эти строки:
    def get_category_url(category):
        category_urls = {
            'пиалы': '/pialki',
            'наборы': '/nabory'
        }
        return category_urls.get(category, '/catalog')
    
    app.jinja_env.globals['get_category_url'] = get_category_url

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500

    return app

app = create_app()