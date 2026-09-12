"""
Demand Radar — веб-портал.

Сейчас: один дашборд, без авторизации (личное использование).
Заготовка под SaaS: таблицы users/saved_watches уже в схеме, роуты /login, /register
закомментированы ниже — раскомментировать и подключить flask-login, когда будет
готова продажа клиентам. Интерфейс дашборда переиспользуется как есть.
"""
from flask import Flask, render_template, request, jsonify
from db import db

app = Flask(__name__)


@app.route("/")
def dashboard():
    days = int(request.args.get("days", 30))
    top_categories = db.get_top_categories(days=days, limit=20)
    recent = db.get_recent_signals(limit=30)
    return render_template("dashboard.html", categories=top_categories, recent=recent, days=days)


@app.route("/category/<name>")
def category_detail(name):
    signals = db.get_recent_signals(category=name, limit=100)
    return render_template("category.html", category=name, signals=signals)


@app.route("/api/categories")
def api_categories():
    days = int(request.args.get("days", 30))
    return jsonify(db.get_top_categories(days=days, limit=50))


@app.route("/api/signals")
def api_signals():
    category = request.args.get("category")
    return jsonify(db.get_recent_signals(category=category, limit=100))


# --- Заготовка под SaaS (пока выключена) ---
# from flask_login import LoginManager, login_user, login_required
# login_manager = LoginManager(app)
#
# @app.route("/register", methods=["GET", "POST"])
# def register(): ...
#
# @app.route("/login", methods=["GET", "POST"])
# def login(): ...
#
# @app.route("/watch", methods=["POST"])
# @login_required
# def add_watch(): ...


if __name__ == "__main__":
    db.init_db()
    app.run(host="0.0.0.0", port=8080, debug=True)
