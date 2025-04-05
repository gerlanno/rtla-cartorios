from re import DEBUG
from flask import Flask
from extensions import db, login_manager, migrate
from cli import init_cli
from config import FLASK_SECRET_KEY, USERS_DB

UPLOAD_FOLDER = 'files'

def create_app():
    
    app = Flask(__name__, template_folder="templates")
    app.config["SQLALCHEMY_DATABASE_URI"] = USERS_DB
    app.secret_key = FLASK_SECRET_KEY
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # Limite de 10MB

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



