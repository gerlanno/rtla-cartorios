from fileinput import filename
import stat
from flask import jsonify
import requests
from config import find_token, db_connect
from utils.logger import Logger
from datetime import datetime, timedelta
import time
import csv
import os
import json


BASE_API_URL = 'http://localhost:5001'

today = datetime.now()

logger = Logger().get_logger()


def check_response(response):
    """Função para checagem de alertas recebedidos do webhook"""

    # Process WhatsApp message
    try:
        entries = response.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value")
                if value:
                    phone_number_id = value["metadata"]["phone_number_id"]
                    # Verifica se foi recebido alguma mensagem, e chama a função de resposta automática
                    if value.get("messages"):
                        for message in value["messages"]:
                            message_id = message["id"]
                            from_number = message["from"]
                            message_body = (
                                message["text"]["body"]
                                if message["type"] == "text"
                                else ""
                            )
                            auto_reply(
                                phone_number_id, from_number, message_id, message_body
                            )
                    # Verifica se chegou alguma atualização de status de mensagens e chama a função de registro de
                    # atualizações
                    elif value.get("statuses"):
                        for status in value["statuses"]:
                            message_id = status["id"]
                            message_status = status["status"]
                            recipient_id = status["recipient_id"]
                            # Em caso de Falha, inserir no banco de dados.
                            if message_status == "failed":
                                recipient_id = status["recipient_id"]
                                for error in status["errors"]:
                                    error_message = error["message"]
                                message_update_status(
                                    message_status,
                                    message_id,
                                    phone_number_id=phone_number_id,
                                    recipient_id=recipient_id,
                                    error_message=error_message,
                                )
                            # Atualiza o status das mensagens já registradas.
                            # Alterado a pedido do Anderson, para registrar todos as etapas da mensagem.
                            message_received(
                                message_id,
                                phone_number_id,
                                recipient_id,
                                message_status,
                            )
    except Exception as e:
        logger.error(f"Erro - {e}")


def auto_reply(phone_number_id, reply_to, message_id, message_body):
    """
    Função responsável por responder automaticamente mensagens recebidas.
    """

    params = [reply_to, phone_number_id, "Resposta automática"]

    try:

        pg = db_connect()
        pg.conectar()
        cursor = pg.conn.cursor()
        query = """
            SELECT 
               count(*)
            FROM message_history 
            WHERE recipient_id = %s AND sender_id = %s AND message_content = %s AND created_at BETWEEN NOW() - INTERVAL '2 days' AND NOW();
                """

        cursor.execute(query, params)
        resultados = cursor.fetchall()

        pg.desconectar()

    except Exception as e:
        logger.error(f"Erro - {e}")

    if resultados[0][0] > 0:

        logger.info(f"Resposta automática já enviada: {message_id}")

    else:
        logger.info(f"Resultado query {resultados}")
        reply_message = """Olá, Eu sou o 🤖 do Atendimento Virtual do *Instituto de Cartórios de Protestos do Ceará - IEPTBCE*, o seu Assistente Virtual para informações. Caso tenha recebido um alerta, favor entre em contato com nosso SAC nos links: \n\nWhatsapp: https://wa.me/5585982009501 \nOu acesse nosso site: https://site.ieptbce.com.br"""

        whatsapp_token = find_token(phone_number_id)

        api_url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"

        # Cabeçalhos da solicitação
        headers = {
            f"Authorization": whatsapp_token,
            "Content-Type": "application/json",
        }
        # Dados da Mensagem
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "context": {"message_id": message_id},
            "to": f"+{reply_to}",
            "type": "text",
            "text": {"preview_url": False, "body": reply_message},
        }

        # Enviar a solicitação POST

        response = requests.post(api_url, headers=headers, json=data)

        logger.info(f"Auto reply: {response.status_code}, {response.text}")
        data = response.json()

        if "messages" in data.keys():
            messages = data.get("messages")
            for data in messages:
                if data.get("id"):
                    message_sended_id = data.get("id")
                    message_status = (
                        data.get("message_status") if data.get("message_status") else ""
                    )
            autoreply_history(
                message_sended_id, phone_number_id, reply_to, message_status
            )

    message_received(
        message_id, reply_to, phone_number_id, "received", message_content=message_body
    )


def autoreply_history(message_id, phone_number_id, recipient, message_status):
    """
    Cria o historico das mensagens enviadas
    Atualiza o campo message_id na tabela devedores com o id da mensagem enviada a ele.

    """
    try:
        pg = db_connect()
        pg.conectar()
        cursor = pg.conn.cursor()
        cursor.execute("BEGIN")
        cursor.execute(
            f"""INSERT INTO 
                        message_history (message_id, sender_id, recipient_id, message_content, message_status) 
                        VALUES 
                        ('{message_id}', '{phone_number_id}', '{recipient}', 'Resposta automática', '{message_status}')"""
        )

        pg.conn.commit()
        pg.desconectar()
    except Exception as e:
        logger.error(f"Erro Inserindo no banco de dados: {e}")


def message_update_status(
    message_status, message_id, phone_number_id="", recipient_id="", error_message=""
):
    """
    Atualiza o status das mensagens enviadas.
    """
    if error_message:
        try:
            pg = db_connect()
            pg.conectar()
            cursor = pg.conn.cursor()

            query = f"""INSERT INTO message_history (message_id, sender_id, recipient_id, error_message, message_status)
                                VALUES (%s, %s, %s,%s,%s);"""

            vars = (
                message_id,
                phone_number_id,
                recipient_id,
                error_message,
                message_status,
            )

            cursor.execute(query, vars)
            pg.conn.commit()

        except Exception as e:

            logger.error(f"Erro - {e}")

        pg.desconectar()

    try:
        message_id = message_id
        message_status = message_status
        pg = db_connect()
        pg.conectar()

        pg.cursor.execute(
            f"""
            UPDATE 
                message_history 
            SET 
                message_status = '{message_status}'
            WHERE 
                message_id='{message_id}'
                        
        """
        )
        pg.conn.commit()
        pg.desconectar()

    except Exception as e:
        logger.error(f"Erro: {e}")


def message_received(
    message_id, sender_id, recipient_id, message_status, message_content=""
):
    """
    Cria o historico das mensagens recebidas

    """

    try:
        pg = db_connect()
        pg.conectar()
        cursor = pg.conn.cursor()

        query = f"""INSERT INTO message_history (message_id, sender_id, recipient_id, message_content, message_status)
                            VALUES (%s, %s, %s,%s,%s);"""

        vars = (message_id, sender_id, recipient_id, message_content, message_status)

        cursor.execute(query, vars)
        pg.conn.commit()

    except Exception as e:
        logger.error(f"Erro - {e}")

    pg.desconectar()


def get_total_disparos(
    telefone=None,
    data_inicio=None,
    data_fim=None,
    nome=None,
    protocolo=None,
    documento=None,
    cartorio=None,
):
    """Conta o total de disparos para calcular páginas."""

    query = """
        WITH status_prioridade AS (
            SELECT 
                ze.messageid,
                mh.message_status,
                ROW_NUMBER() OVER (
                    PARTITION BY ze.messageid
                    ORDER BY 
                        CASE mh.message_status
                            WHEN 'read' THEN 1
                            WHEN 'delivered' THEN 2
                            WHEN 'sent' THEN 3
                            WHEN 'pending' THEN 4                           
                            ELSE 5
                        END
                ) as prioridade_rank
            FROM zapenviados ze
            LEFT JOIN message_history mh ON mh.message_id = ze.messageid
            WHERE mh.message_status <> 'failed'
        )
        SELECT COUNT(ze.messageid)
        FROM zapenviados ze
        LEFT JOIN status_prioridade sp ON sp.messageid = ze.messageid AND sp.prioridade_rank = 1
        LEFT JOIN message_history mh ON mh.message_id = ze.messageid 
            AND mh.message_status = sp.message_status
        LEFT JOIN titulos t ON t.id = ze.titulo_id
        LEFT JOIN devedores d ON d.titulo_id = t.id
        WHERE 1=1
        AND mh.message_status <> 'failed'		
        AND LENGTH(REGEXP_REPLACE(d.documento, '[^0-9]', '', 'g')) = 11
    """

    params = []
    
    
    if telefone:
        query += " AND ze.whatsapp LIKE %s"
        params.append(f"%{telefone}%")
    if data_inicio:
        data_inicio = f"{data_inicio} 00:00:01"
        query += " AND ze.datainsert >= %s"
        params.append(data_inicio)
    if data_fim:
        data_fim = f"{data_fim} 23:59:59"
        query += " AND ze.datainsert <= %s"
        params.append(data_fim)
    if nome:
        query += " AND d.nome ILIKE %s"
        params.append(f"%{nome}%")
    if protocolo:
        query += " AND t.protocolo = %s"
        params.append(protocolo)
    if documento:
        query += " AND d.documento = %s"
        params.append(documento)
    if cartorio:
        query += " AND t.cartorio_id = %s"
        params.append(cartorio)

    # query += " AND mh.message_status <> 'failed'"

    try:
        pg = db_connect()
        pg.conectar()
        cursor = pg.conn.cursor()
        cursor.execute(query, params)
        total = cursor.fetchone()[0]

    except Exception as e:
        logger.error(f"Erro ao contar disparos: {e}")
        return 0
    finally:
        pg.desconectar()
    return total


def get_disparos(
    page=1,
    ITEMS_PER_PAGE=10,
    telefone=None,
    data_inicio=None,
    data_fim=None,
    nome=None,
    protocolo=None,
    documento=None,
    cartorio=None,
    save_results=False,
):
    """
    Retorna uma lista com o histórico de disparos realizados incluindo informações do protocolo
    """
    
    params = []

    try:
        pg = db_connect()
        pg.conectar()
        cursor = pg.conn.cursor()

        query = f"""
            WITH status_prioridade AS (
                SELECT 
                    ze.messageid,
                    mh.message_status,
                    ROW_NUMBER() OVER (
                        PARTITION BY ze.messageid
                        ORDER BY 
                            CASE mh.message_status
                                WHEN 'read' THEN 1
                                WHEN 'delivered' THEN 2
                                WHEN 'sent' THEN 3
                                WHEN 'pending' THEN 4                                
                                ELSE 5
                            END
                    ) as prioridade_rank
                FROM zapenviados ze
                LEFT JOIN message_history mh ON mh.message_id = ze.messageid
                WHERE mh.message_status <> 'failed'
            )
            SELECT 
                t.protocolo,
                d.documento,
                d.nome,
                ze.whatsapp as telefone,
                sp.message_status,
                TO_CHAR(ze.datainsert, 'DD/MM/YYYY HH24:MI:SS') as data
            FROM zapenviados ze
            LEFT JOIN status_prioridade sp ON sp.messageid = ze.messageid AND sp.prioridade_rank = 1
            LEFT JOIN message_history mh ON mh.message_id = ze.messageid 
                AND mh.message_status = sp.message_status
            LEFT JOIN titulos t ON t.id = ze.titulo_id
            LEFT JOIN devedores d ON d.titulo_id = t.id
            WHERE 1=1          
        """
        
        
        if telefone:
            query += " AND ze.whatsapp LIKE %s"
            params.append(f"%{telefone}%")
        if data_inicio:
            data_inicio = f"{data_inicio} 00:00:01"
            query += " AND ze.datainsert >= %s"
            params.append(data_inicio)
        if data_fim:
            data_fim = f"{data_fim} 23:59:59"
            query += " AND ze.datainsert <= %s"
            params.append(data_fim)
        if nome:
            query += " AND d.nome ILIKE %s"
            params.append(f"%{nome}%")
        if protocolo:
            query += " AND t.protocolo = %s"
            params.append(protocolo)
        if documento:
            query += " AND d.documento = %s"
            params.append(documento)
        if cartorio:
            query += " AND t.cartorio_id = %s"
            params.append(cartorio)

        query += " AND mh.message_status <> 'failed'"
        query += f" AND LENGTH(REGEXP_REPLACE(d.documento, '[^0-9]', '', 'g')) = 11"

        query += " ORDER BY ze.datainsert DESC"

        if not save_results:

            offset = (page - 1) * ITEMS_PER_PAGE
            query += " LIMIT %s OFFSET %s"

            params.extend([ITEMS_PER_PAGE, offset])

        cursor.execute(query, params)

        results = cursor.fetchall()

        message_list = []
        for row in results:
            reply_details = check_exists_reply(row[3])

            message = {
                "protocolo": row[0] or "",
                "documento": row[1] or "",
                "nome": row[2] or "",
                "telefone": row[3] or "",
                "status": row[4] or "",
                "data": row[5] or "",
                "reply_details": reply_details,
            }

            message_list.append(message)

        return message_list

    except Exception as e:
        logger.error(f"Erro ao buscar histórico de mensagens: {e}")
        return []

    finally:
        pg.desconectar()


def check_exists_reply(sender_id):
    """
    Retorna os detalhes das mensagens de um remetente específico
    """
    sender = sender_id[-8:]

    params = [f"%{sender}%"]
    try:
        pg = db_connect()
        pg.conectar()
        cursor = pg.conn.cursor()
        query = """
            SELECT 
                message_content,
                message_status,
                TO_CHAR(created_at, 'DD/MM/YYYY HH24:MI:SS') as data
            FROM message_history 
            WHERE sender_id LIKE %s
            ORDER BY created_at DESC
        """
        cursor.execute(query, params)
        results = cursor.fetchall()

        if results:
            messages = []
            for row in results:
                messages.append({"content": row[0], "status": row[1], "data": row[2]})

            pg.desconectar()
            return messages

        pg.desconectar()
        return []

    except Exception as e:
        logger.error(f"Erro ao buscar detalhes da mensagem: {e}")
        return []
    finally:
        pg.desconectar()


def get_cartorios():
    """
    Retorna uma lista com todos os cartórios cadastrados
    """
    try:
        pg = db_connect()
        pg.conectar()
        cursor = pg.conn.cursor()
        query = """
            SELECT id, nome FROM cartorio
        """
        cursor.execute(query)
        results = cursor.fetchall()
        return results
    except Exception as e:
        logger.error(f"Erro ao buscar cartórios: {e}")
        return []
    finally:
        pg.desconectar()


def export_to_file(
    telefone=None,
    data_inicio=None,
    data_fim=None,
    nome=None,
    protocolo=None,
    documento=None,
    cartorio=None,
):

    params = []

    try:
        pg = db_connect()
        pg.conectar()
        cursor = pg.conn.cursor()

        query = f"""
                WITH status_prioridade AS (
                    SELECT 
                        ze.messageid,
                        mh.message_status,
                        ROW_NUMBER() OVER (
                            PARTITION BY ze.messageid
                            ORDER BY 
                                CASE mh.message_status
                                    WHEN 'read' THEN 1
                                    WHEN 'delivered' THEN 2
                                    WHEN 'sent' THEN 3
                                    WHEN 'pending' THEN 4                                
                                    ELSE 5
                                END
                        ) as prioridade_rank
                    FROM zapenviados ze
                    LEFT JOIN message_history mh ON mh.message_id = ze.messageid
                    WHERE mh.message_status <> 'failed'
                )
                SELECT 
                    t.protocolo,
                    d.documento,
                    d.nome,
                    ze.whatsapp as telefone,
                    sp.message_status,
                    TO_CHAR(ze.datainsert, 'DD/MM/YYYY HH24:MI:SS') as data
                FROM zapenviados ze
                LEFT JOIN status_prioridade sp ON sp.messageid = ze.messageid AND sp.prioridade_rank = 1
                LEFT JOIN message_history mh ON mh.message_id = ze.messageid 
                    AND mh.message_status = sp.message_status
                LEFT JOIN titulos t ON t.id = ze.titulo_id
                LEFT JOIN devedores d ON d.titulo_id = t.id
                WHERE 1=1          
            """

        if telefone:
            query += " AND ze.whatsapp LIKE %s"
            params.append(f"%{telefone}%")
        if data_inicio:
            data_inicio = f"{data_inicio} 00:00:01"
            query += " AND ze.datainsert >= %s"
            params.append(data_inicio)
        if data_fim:
            data_fim = f"{data_fim} 23:59:59"
            query += " AND ze.datainsert <= %s"
            params.append(data_fim)
        if nome:
            query += " AND d.nome ILIKE %s"
            params.append(f"%{nome}%")
        if protocolo:
            query += " AND t.protocolo = %s"
            params.append(protocolo)
        if documento:
            query += " AND d.documento = %s"
            params.append(documento)
        if cartorio:
            query += " AND t.cartorio_id = %s"
            params.append(cartorio)

        query += " AND mh.message_status <> 'failed'"
        query += f" AND LENGTH(REGEXP_REPLACE(d.documento, '[^0-9]', '', 'g')) = 11"

        query += " ORDER BY ze.datainsert DESC"

        cursor.execute(query, params)

        results = cursor.fetchall()

        message_list = []
        for row in results:

            message = {
                "protocolo": row[0] or "",
                "documento": row[1] or "",
                "nome": row[2] or "",
                "telefone": row[3] or "",
                "status": row[4] or "",
                "data": row[5] or "",
            }

            message_list.append(message)

        output = salvar_csv(message_list, cartorio=cartorio if cartorio else None)
        return output
    except Exception as e:
        logger.error(f"Erro ao buscar histórico de mensagens: {e}")
        return []

    finally:
        pg.desconectar()


def salvar_csv(message_list, cartorio="ALL"):
    """Salva os dados da message_list em um arquivo CSV."""

    FILES_DIR = "files"
    filename = f"[{cartorio}]-ExportResults{today.strftime('%d%m%Y-%H%M%S')}.csv"

    if not message_list:
        logger.info("Nada para salvar.")
        return

    cabecalhos = ["protocolo", "documento", "nome", "telefone", "status", "data"]

    with open(
        os.path.join(FILES_DIR, filename), mode="w", newline="", encoding="utf-8"
    ) as arquivo_csv:
        writer = csv.DictWriter(arquivo_csv, fieldnames=cabecalhos)
        writer.writeheader()
        writer.writerows(message_list)

    return {"file_dir": FILES_DIR, "filename": filename}


def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'xml'}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def delete_xml(filename):
    FILES_DIR = 'files'
    try:
        os.remove(os.path.join(FILES_DIR, filename))
        print("tentando remover")
        return {"sucess": True}
    except Exception as e:
        print(e)
        return {"error": e}
    

def importar_xml():
    
    url = f"{BASE_API_URL}/extrair"
    response = requests.request(method="GET", url=url)
   
    return json.loads(response.text)

