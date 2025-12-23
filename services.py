from fileinput import filename
import stat
from flask import jsonify
import requests
from config import find_token, db_connect
from utils.logger import Logger
from datetime import datetime, timedelta
import pandas as pd
import time
import csv
import os
import json


BASE_API_URL = "http://localhost:5001"

today = datetime.now()

logger = Logger().get_logger()


def check_response(response):
    
    # Tratamentos do callback do webhook do WhatsApp Business
    
    try:
        entries = response.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value")

                # Envia por email alterações na classificação de qualidade das templates
                if "message_template_quality_update" in change.values():
                    template_id = str(value.get("message_template_id"))
                    template_name = str(value.get("message_template_name"))
                    new_quality_score = str(value.get("new_quality_score"))
                    logger.info(f"ATUALIZAÇÃO DE QUALIDADE DA TEMPLATE: Template: {template_name}, ID: {template_id}, Nova qualidade: {new_quality_score}")

                if value:
                    phone_number_id = value["metadata"]["phone_number_id"]
                    # Verifica se foi recebido alguma mensagem, e chama a função de resposta automática
                    if value.get("messages"):
                        for message in value["messages"]:
                            
                            if message.get("button"):
                                if message.get("button").get("payload"):
                                    payload = message.get("button").get("payload").lower()
                                    if payload == "sair":
                                        # A chave correta no webhook de retorno é 'id' dentro de 'context'
                                        message_context = message.get("context", {})
                                        messageid_original = message_context.get("id")
                                        
                                        nr_whatsapp = message.get("from", "")
                                        if messageid_original:
                                            descadastrar_numero_sair(messageid_original, nr_whatsapp)
                                        else:
                                            logger.warning(f"Botão SAIR clicado por {nr_whatsapp} mas sem context.id")
                            
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
                        for i, status in enumerate(value["statuses"]):
                                                      
                            message_id = status["id"]
                            message_status = status["status"]
                            recipient_id = status["recipient_id"]
                            # Em caso de Falha, inserir no banco de dados.
                            if message_status == "failed":                                
                                if status["errors"]:                                    
                                    error_message = status["errors"][0]["message"]
                                    error_code = status["errors"][0]["code"]
                                message_update_status(
                                    message_status,
                                    message_id,
                                    phone_number_id=phone_number_id,
                                    recipient_id=recipient_id,
                                    error_message=error_message,
                                    error_code=error_code,
                                )
                                continue
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

def descadastrar_numero_sair(message_id, nr_whatsapp):
    """
    Função responsável por descadastrar um número da lista de disparos que tiver clicado no botão de sair.
    """
    logger.info(f"Solicitado descadastramento do Whatsapp: {nr_whatsapp} - ID: {message_id}")
    try:
        pg = db_connect()
        pg.conectar()
        cursor = pg.conn.cursor()
        cursor.execute("SELECT whatsapp FROM zapenviados WHERE messageid = %s", (message_id,)) 
        whatsapp = cursor.fetchone()        
        whatsapp = whatsapp[0][-8:] if whatsapp else None      

        if whatsapp:
            cursor.execute("UPDATE contatos SET validado = false, detalhes = 'botão sair' WHERE telefone LIKE %s", (f"%{whatsapp}%",))
            pg.conn.commit()
            logger.info(f"Número descadastrado: {whatsapp}")
        else:
            logger.info(f"Número não encontrado: {whatsapp}")
        pg.desconectar()
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
        # Checar se a resposta automática já foi enviada pelo menos a dois dias, para não enviar repetidamente.
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

        # Buscar o token da acc de acordo com o phone_number_id
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
    message_status,
    message_id,
    phone_number_id="",
    recipient_id="",
    error_message="",
    error_code="",
):
    """
    Atualiza o status das mensagens enviadas.
    """
    if error_message:
        try:
            pg = db_connect()
            pg.conectar()
            cursor = pg.conn.cursor()

            query = f"""INSERT INTO message_history (message_id, sender_id, recipient_id, error_message,error_code, message_status)
                                VALUES (%s, %s, %s,%s,%s,%s);"""

            vars = (
                message_id,
                phone_number_id,
                recipient_id,
                error_message,
                error_code,
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

def get_base_query(select_clause):
    """
    Monta a estrutura correta: CTE -> SELECT (argumento) -> FROM/JOINS -> WHERE base
    Correção aplicada: JOIN via tabela de contatos para evitar produto cartesiano em títulos com múltiplos devedores.
    """
    return f"""
        WITH mh_ranked AS (
            SELECT
                mh.message_id,
                mh.message_status,
                mh.created_at,
                ROW_NUMBER() OVER (
                    PARTITION BY mh.message_id 
                    ORDER BY 
                        CASE mh.message_status
                            WHEN 'read' THEN 1
                            WHEN 'delivered' THEN 2
                            WHEN 'sent' THEN 3
                            ELSE 4
                        END ASC,
                        mh.created_at DESC
                ) AS rn
            FROM message_history mh
            WHERE mh.message_status IN ('read', 'delivered', 'sent')
        )
        {select_clause}
        FROM zapenviados ze
        INNER JOIN mh_ranked mhr ON mhr.message_id = ze.messageid AND mhr.rn = 1
        
        -- INICIO DA CORREÇÃO: Filtragem via Contatos --
        INNER JOIN contatos c ON c.telefone = ze.whatsapp
        -- Vincula o documento do contato ao devedor DESTE título específico (ze.titulo_id)
        INNER JOIN devedores d ON d.documento = c.documento AND d.titulo_id = ze.titulo_id
        -- FIM DA CORREÇÃO --

        LEFT JOIN titulos t ON t.id = ze.titulo_id
        
        WHERE 1=1
        AND LENGTH(d.documento) = 11
    """

def apply_filters(query, params, telefone, data_inicio, data_fim, nome, protocolo, documento, cartorio):
    """Aplica os filtros comuns a todas as queries"""
    if telefone:
        query += " AND ze.whatsapp LIKE %s"
        params.append(f"%{telefone}%")
    if data_inicio:
        # Garante formato correto se vier só a data YYYY-MM-DD
        if len(data_inicio) <= 10: data_inicio = f"{data_inicio} 00:00:01"
        query += " AND ze.datainsert >= %s"
        params.append(data_inicio)
    if data_fim:
        if len(data_fim) <= 10: data_fim = f"{data_fim} 23:59:59"
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
    
    return query, params




def __get_total_disparos(
    telefone=None,
    data_inicio=None,
    data_fim=None,
    nome=None,
    protocolo=None,
    documento=None,
    cartorio=None,
):
    """Conta o total de disparos para calcular páginas (considera apenas o último status por message_id)."""

    query = """
        WITH mh_ranked AS (
            SELECT
                mh.message_id,
                mh.message_status,
                ROW_NUMBER() OVER (PARTITION BY mh.message_id ORDER BY mh.created_at DESC) AS rn
            FROM message_history mh
            -- opcional: filtrar aqui para reduzir quantidade scaneada, ex: WHERE mh.message_status <> 'failed'
        )
        SELECT COUNT(*)
        FROM zapenviados ze
        LEFT JOIN titulos t ON t.id = ze.titulo_id
        LEFT JOIN devedores d ON d.titulo_id = t.id
        LEFT JOIN mh_ranked mhr ON mhr.message_id = ze.messageid AND mhr.rn = 1
        WHERE 1=1
          AND mhr.message_status = 'sent'
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

    try:
        pg = db_connect()
        pg.conectar()
        cursor = pg.conn.cursor()
        cursor.execute(query, params)
        total = cursor.fetchone()[0] or 0
    except Exception as e:
        logger.error(f"Erro ao contar disparos: {e}")
        return 0
    finally:
        pg.desconectar()
    return total

def get_total_disparos(telefone=None, data_inicio=None, data_fim=None, nome=None, protocolo=None, documento=None, cartorio=None):
    params = []
    
    # AQUI ESTAVA O ERRO: Agora passamos o SELECT para dentro da função base
    query = get_base_query("SELECT COUNT(*)")

    # Aplica os filtros (continua igual)
    query, params = apply_filters(query, params, telefone, data_inicio, data_fim, nome, protocolo, documento, cartorio)

    try:
        pg = db_connect()
        pg.conectar()
        cursor = pg.conn.cursor()
        cursor.execute(query, params)
        total = cursor.fetchone()[0] or 0
        return total
    except Exception as e:
        logger.error(f"Erro ao contar disparos: {e}")
        return 0
    finally:
        pg.desconectar()


def __get_disparos(
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
            WITH mh_ranked AS (
  SELECT
    mh.*,
    ROW_NUMBER() OVER (PARTITION BY mh.message_id ORDER BY mh.created_at DESC) AS rn
  FROM message_history mh
)
SELECT
  t.protocolo,
  d.documento,
  d.nome,
  ze.whatsapp AS telefone,
  mhr.message_status,
  TO_CHAR(ze.datainsert, 'DD/MM/YYYY HH24:MI:SS') AS data,
  CASE mhr.message_status
      WHEN 'read' THEN 1
      WHEN 'delivered' THEN 2
      WHEN 'sent' THEN 3
      ELSE 99
  END AS status_priority
FROM zapenviados ze
LEFT JOIN titulos t ON t.id = ze.titulo_id
LEFT JOIN devedores d ON d.titulo_id = t.id
LEFT JOIN mh_ranked mhr ON mhr.message_id = ze.messageid AND mhr.rn = 1
WHERE 1=1 
AND mhr.message_status IN ('sent','delivered','read')      
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

        #query += " AND mh2.message_status <> 'failed'"
        query += f" AND LENGTH(REGEXP_REPLACE(d.documento, '[^0-9]', '', 'g')) = 11"

        
        query += " ORDER BY ze.datainsert DESC"        #-- menor -> maior = prioridade mais alta primeiro / dentro da mesma prioridade, mais recente primeir
     

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
   
            }

            message_list.append(message)

        return message_list

    except Exception as e:
        logger.error(f"Erro ao buscar histórico de mensagens: {e}")
        return []

    finally:
        pg.desconectar()

def get_disparos(page=1, ITEMS_PER_PAGE=10, telefone=None, data_inicio=None, data_fim=None, nome=None, protocolo=None, documento=None, cartorio=None, save_results=False):
    params = []
    
    # Define as colunas que você quer retornar
    cols = """
        SELECT
            t.protocolo,
            d.documento,
            d.nome,
            ze.whatsapp AS telefone,
            mhr.message_status,
            TO_CHAR(ze.datainsert, 'DD/MM/YYYY HH24:MI:SS') AS data
    """
    
    # Monta a query na ordem certa
    query = get_base_query(cols)

    # Filtros
    query, params = apply_filters(query, params, telefone, data_inicio, data_fim, nome, protocolo, documento, cartorio)

    query += " ORDER BY ze.datainsert DESC"

    if not save_results:
        offset = (page - 1) * ITEMS_PER_PAGE
        query += " LIMIT %s OFFSET %s"
        params.extend([ITEMS_PER_PAGE, offset])

    try:
        pg = db_connect()
        pg.conectar()
        cursor = pg.conn.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        # ... (resto do código de mapeamento para dicionário igual) ...
        
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
            
        return message_list

    except Exception as e:
        logger.error(f"Erro ao buscar histórico: {e}")
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






def buscar_contato_por_telefone(telefone):
    """
    Busca contatos que contenham o telefone informado.
    Retorna lista de dicionários com: nome, documento, telefone, validado.
    """
    try:
        pg = db_connect()
        pg.conectar()
        cursor = pg.conn.cursor()

        # Join com devedores para pegar o nome
        # DISTINCT para evitar duplicados se o mesmo devedor tiver múltiplos títulos
        query = """
            SELECT DISTINCT ON (c.documento, c.telefone)
                d.nome,
                c.documento,
                c.telefone,
                c.validado
            FROM contatos c
            LEFT JOIN devedores d ON c.documento = d.documento
            WHERE c.telefone LIKE %s
            LIMIT 50
        """
        
        cursor.execute(query, (f"%{telefone}%",))
        results = cursor.fetchall()
        
        contatos = []
        for row in results:
            contatos.append({
                "nome": row[0] or "Não identificado",
                "documento": row[1],
                "telefone": row[2],
                "validado": row[3]
            })
            
        return contatos

    except Exception as e:
        logger.error(f"Erro ao buscar contato: {e}")
        return []
    finally:
        pg.desconectar()


def atualizar_validacao_contato(telefone, documento, validado):
    """
    Atualiza o status de validação de um contato.
    """
    try:
        pg = db_connect()
        pg.conectar()
        cursor = pg.conn.cursor()

        query = """
            UPDATE contatos 
            SET validado = %s 
            WHERE telefone = %s AND documento = %s
        """
        
        cursor.execute(query, (validado, telefone, documento))
        pg.conn.commit()
        
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar contatos: {e}")
        return False
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
    """
    Exporta todos os dados filtrados usando a mesma lógica (CTE) da visualização e contagem,
    garantindo que os números batam e não haja duplicatas.
    """
    params = []

    # 1. Define as colunas (mesmas do get_disparos)
    cols = """
        SELECT
            t.protocolo,
            d.documento,
            d.nome,
            ze.whatsapp AS telefone,
            mhr.message_status,
            TO_CHAR(ze.datainsert, 'DD/MM/YYYY HH24:MI:SS') AS data
    """

    # 2. Monta a query na ordem correta (WITH -> SELECT -> FROM)
    query = get_base_query(cols)

    # 3. Aplica os filtros (usando a função auxiliar criada anteriormente)
    query, params = apply_filters(query, params, telefone, data_inicio, data_fim, nome, protocolo, documento, cartorio)

    # 4. Ordenação (sem paginação/limit)
    query += " ORDER BY ze.datainsert DESC"

    try:
        pg = db_connect()
        pg.conectar()
        cursor = pg.conn.cursor()
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

        # Chama a sua função existente que gera o arquivo
        output = salvar_csv(message_list, cartorio=cartorio if cartorio else None)
        return output

    except Exception as e:
        logger.error(f"Erro ao exportar histórico: {e}")
        return []

    finally:
        pg.desconectar()


def salvar_csv(message_list, cartorio=None):
    """Salva os dados da message_list em um arquivo CSV."""

    FILES_DIR = "files"
    filename = f"[{cartorio if cartorio else 'TODOS'}]-ExportResults{today.strftime('%d%m%Y-%H%M%S')}.csv"

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
    ALLOWED_EXTENSIONS = {"xml"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def delete_xml(filename):
    FILES_DIR = "files"
    try:
        os.remove(os.path.join(FILES_DIR, filename))
        print("tentando remover")
        return {"sucess": True}
    except Exception as e:
        print(e)
        return {"error": e}


def agendar_disparo(data_agendamento, usuario, cartorio, arquivo):

    try:
        pg = db_connect()
        pg.conectar()
        cursor = pg.conn.cursor()
        vars = (data_agendamento, usuario, cartorio, arquivo)

        query = f"""
            INSERT INTO 
                public.agendamentos
                (
                data_disparo, usuario, cartorio_id, nome_arquivo
                )
                VALUES 
                (%s, %s, %s, %s);
        """

        cursor.execute(query=query, vars=vars)
        pg.conn.commit()
        pg.desconectar()


    except Exception as e:
        return jsonify({"Erro": f"Erro inserindo agendamento {e}"})
    

    return {"Status": "Sucesso"}
