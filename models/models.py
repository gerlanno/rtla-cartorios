from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from extensions import db

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(128))
    nome = db.Column(db.String(80))
    is_admin = db.Column(db.Boolean, default=False)
    cartorio_id = db.Column(db.Integer, nullable=True)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)