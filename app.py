from flask import Flask
from extensions import db, login_manager, migrate
from cli import init_cli


def create_app():
    app = Flask(__name__, template_folder="templates")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
    app.secret_key = "secret*Key@Flask"

    # Inicializa as extensões
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # Registra as rotas
    from routes import setup_routes

    setup_routes(app, db)

    # Inicializa os comandos CLI
    init_cli(app)

    return app



