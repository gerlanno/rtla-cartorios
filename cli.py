import click
from flask.cli import with_appcontext
from extensions import db
from models.models import Usuario
# Certifique-se de importar as funções de hash de senha
from werkzeug.security import generate_password_hash, check_password_hash

def init_cli(app):
    # --- COMANDO PARA CRIAR ADMINISTRADOR (JÁ EXISTENTE) ---
    @app.cli.command("criar-admin")
    @click.option('--email', prompt='Email do admin')
    @click.option('--senha', prompt='Senha do admin', hide_input=True)
    @click.option('--nome', prompt='Nome do admin')
    @with_appcontext
    def criar_admin(email, senha, nome):
        """Cria um usuário administrador."""
        try:
            if Usuario.query.filter_by(email=email).first():
                click.echo('Erro: Email já cadastrado.')
                return

            admin = Usuario(email=email, nome=nome, is_admin=True)
            admin.set_senha(senha)
            db.session.add(admin)
            db.session.commit()
            click.echo('Administrador criado com sucesso!')
        except Exception as e:
            db.session.rollback()
            click.echo(f'Erro ao criar administrador: {str(e)}')

    # --- NOVO COMANDO PARA CRIAR USUÁRIO COMUM ---
    @app.cli.command("criar-usuario")
    @click.option('--email', prompt='Email do usuário')
    @click.option('--senha', prompt='Senha do usuário', hide_input=True)
    @click.option('--nome', prompt='Nome do usuário')
    @click.option('--cartorio', prompt='ID do Cartório', type=int)
    @with_appcontext
    def criar_usuario(email, senha, nome, cartorio):
        """Cria um usuário comum associado a um cartório."""
        try:
            if Usuario.query.filter_by(email=email).first():
                click.echo('Erro: Email já cadastrado.')
                return
            
            # Validação simples para o ID do cartório
            if not cartorio or cartorio <= 0:
                click.echo('Erro: ID do Cartório é obrigatório e deve ser um número positivo.')
                return

            # Cria o usuário com is_admin=False (padrão) e associa o cartorio_id
            usuario = Usuario(
                email=email, 
                nome=nome, 
                cartorio_id=cartorio,
                is_admin=False # Explícito para clareza, mas já é o default
            )
            usuario.set_senha(senha)
            db.session.add(usuario)
            db.session.commit()
            click.echo(f'Usuário "{nome}" para o cartório ID {cartorio} criado com sucesso!')
        except Exception as e:
            db.session.rollback()
            click.echo(f'Erro ao criar usuário: {str(e)}')