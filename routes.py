import csv
import os
from urllib import response
from sqlalchemy.exc import IntegrityError
from flask import (
    flash,
    redirect,
    request,
    render_template,
    jsonify,
    url_for,
    Flask,
    session,
)
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from models.models import Usuario
from services import *

from utils.logger import Logger

logger = Logger().get_logger()


def setup_routes(app, db):

    login_manager = LoginManager()
    login_manager.init_app(app)

    @app.route("/", methods=["GET", "POST"])
    def webhook():
        """
        Recebe os dados do webhook da meta, com as atualizações
        sobre as mensagens do Whatsapp business.
        """
        if request.method == "GET":
            mode = request.args.get("hub.mode")
            token = request.args.get("hub.verify_token")
            challenge = request.args.get("hub.challenge")

            if mode and token:
                if mode == "subscribe" and token == "Token$Verificacao$hook":
                    return challenge, 200
                else:
                    return "Forbidden", 403
            else:
                return redirect(url_for("login"))
        elif request.method == "POST":
            data = request.get_json()
            if data:

                # message_update_status(data) # Chama a função de atualização de status
                logger.info(data)
                check_response(data)

                return jsonify({"status": "success"}), 200
            return "<h1>Bad Request</h1>", 400  # Para o caso de dados inválidos no POST

    @app.route("/disparos", methods=["GET", "POST"])
    @login_required
    def disparos():
        ITEMS_PER_PAGE = 10
        """
        Recebe os disparos da API
        """
        if current_user.cartorio_id:
            cartorio_user = current_user.cartorio_id
           
        else:
            cartorio_user = None

        if request.method == "GET":
            telefone = request.args.get("telefone", None)
            data_inicio = request.args.get("data_inicio", None)
            data_fim = request.args.get("data_fim", None)
            nome = request.args.get("nome", None)
            protocolo = request.args.get("protocolo", None)
            documento = request.args.get("documento", None)
            if current_user.is_admin:
                cartorio = request.args.get("cartorio", None)
            else:
                cartorio = cartorio_user
            page = request.args.get("page", 1, type=int)
            disparos = get_disparos(
                page,
                ITEMS_PER_PAGE,
                telefone,
                data_inicio,
                data_fim,
                nome,
                protocolo,
                documento,
                cartorio,
            )
            total_disparos = get_total_disparos(
                telefone, data_inicio, data_fim, nome, protocolo, documento, cartorio
            )
            total_pages = (
                total_disparos + ITEMS_PER_PAGE - 1
            ) // ITEMS_PER_PAGE  # Arredondando para cima

            return render_template(
                "disparos.html",
                total_disparos=total_disparos,
                disparos=disparos,
                page=page,
                total_pages=total_pages,
                telefone=telefone,
                data_inicio=data_inicio,
                data_fim=data_fim,
                nome=nome,
                protocolo=protocolo,
                documento=documento,
                cartorio=cartorio,
            )
        return "<h1>Bad Request</h1>", 400

    @app.route("/registro", methods=["GET", "POST"])
    @login_required
    def registro():
        # Verifica se o usuário atual é admin
        if not current_user.is_admin:
            flash(
                "Acesso não autorizado. Apenas administradores podem registrar novos usuários.",
                "danger",
            )
            return redirect(url_for("disparos"))

        if request.method == "GET":
            cartorios = get_cartorios()
            return render_template("registro.html", cartorios=cartorios)

        if request.method == "POST":
            email = request.form.get("email")
            senha = request.form.get("senha")
            nome = request.form.get("nome")
            cartorio = request.form.get("cartorio")

            # Validações básicas
            if not email or not senha or not nome:
                flash("Todos os campos são obrigatórios", "danger")
                return redirect(url_for("registro"))

            # Verifica se o email já existe
            if Usuario.query.filter_by(email=email).first():
                flash("Email já cadastrado", "danger")
                return redirect(url_for("registro"))

            # Cria novo usuário (não admin por padrão)
            novo_usuario = Usuario(
                email=email,
                nome=nome,
                is_admin=False,  # Garante que novos usuários não são admin
                cartorio_id=int(cartorio),
            )
            novo_usuario.set_senha(senha)

            try:
                db.session.add(novo_usuario)
                db.session.commit()
                flash(f"Usuário {nome} registrado com sucesso!", "success")

                return redirect(url_for("disparos"))
            except Exception as e:
                db.session.rollback()
                logger.error(f"Erro ao registrar usuário: {str(e)}")
                flash(f"Erro ao registrar usuário: {str(e)}", "danger")
                return redirect(url_for("registro"))

    # Carrega o usuário a partir do ID armazenado na sessão
    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    # Rota de login
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            erro = {"error": "Você já está logado!"}
            return render_template("login.html", erro=erro)

        if request.method == "GET":
            return render_template("login.html")

        if request.method == "POST":
            nome = request.form.get("nome")
            senha = request.form.get("senha")

            usuario = Usuario.query.filter_by(nome=nome).first()

            # Verifica se o usuário existe e a senha é válida
            if usuario and usuario.verificar_senha(senha):
                login_user(usuario)
                return redirect(url_for("disparos"))

            flash("Email ou senha inválidos")
            return redirect(url_for("login"))

    # Rota de logout
    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("Logout realizado com sucesso")
        return redirect(url_for("login"))

    @app.route("/get_messages/<telefone>")
    @login_required
    def get_messages(telefone):
        messages = check_exists_reply(telefone)
        return jsonify(messages)
