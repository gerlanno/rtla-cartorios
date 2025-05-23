
from email.message import EmailMessage
import smtplib
import ssl
import os
import mimetypes
from config import email_config



def info_template_quality(template_name="", template_id="", quality=""):
    # Configuração do servidor SMTP
    smtp_password = email_config["EMAIL_PASSWORD"] 
    smtp_username = email_config["FROM_EMAIL"]
    to_email = email_config["TO_EMAIL"]
    smtp_server = "smtp.gmail.com"
    smtp_port = 465
    
    message = EmailMessage()
    message["From"] = smtp_username
    message["To"] = to_email
    message["Subject"] = "[ATENÇÃO] Alteração de qualidade da template"

    message.set_content(f"Atualização de qualidade da template:\n\nTemplate: {template_name}\nTemplate_ID: {template_id}\n Novo índice de qualidade: {quality}")


    with smtplib.SMTP_SSL(smtp_server, smtp_port, context=ssl.create_default_context()) as server:
        try:
            server.login(smtp_username, smtp_password)
            server.send_message(message)
        except Exception as e:
            print(f"Erro ao enviar email: {e}")
    print("Email enviado com sucesso")




