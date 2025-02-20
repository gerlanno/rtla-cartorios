import click
from flask.cli import with_appcontext
from extensions import db
from models.models import Usuario

def init_cli(app):
    @app.cli.command("criar-admin")
    @click.option('--email', prompt='Email do admin')
    @click.option('--senha', prompt='Senha do admin', hide_input=True)
    @click.option('--nome', prompt='Nome do admin')
    @with_appcontext
    def criar_admin(email, senha, nome):
        """Cria um usuário administrador."""
        try:
            if Usuario.query.filter_by(email=email).first():
                click.echo('Erro: Email já cadastrado')
                return

            admin = Usuario(email=email, nome=nome, is_admin=True)
            admin.set_senha(senha)
            db.session.add(admin)
            db.session.commit()
            click.echo('Administrador criado com sucesso!')
        except Exception as e:
            db.session.rollback()
            click.echo(f'Erro ao criar administrador: {str(e)}')