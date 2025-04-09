from email import message
import requests
import json
from config import find_token, db_connect
from tqdm import tqdm

url = "http://localhost:11434/api/generate"


def agente_verificador(whatsapp="", message=""):
  
    data = str({"telefone": whatsapp, "message": message})

  

    prompt = f"""
                    #Você é responsável por analisar as respostas recebidas em mensagens enviadas via WhatsApp pela empresa. Seu objetivo é identificar se a mensagem foi enviada para o número errado, com base na resposta recebida do destinatário.

                    ##Você receberá uma entrada no seguinte formato:
                    
                    "telefone": "5585992058133",
                    "message": "ola este numero nao me pertence, favor retirar da sua lista"
                    

                    ##Após analisar o conteúdo da mensagem, retorne:
                    - False se identificar que a resposta indica claramente que a mensagem foi enviada para a pessoa errada (por exemplo: "este número não me pertence", "mensagem errada", "não sou essa pessoa", "SAIR", retire meu nome da sua base de dados, isso é golpe, etc.).
                    - True se não houver indícios suficientes de que a mensagem foi enviada para a pessoa errada.

                    ##Importante: Responda apenas com True ou False, e nada mais.
                    ##Só retorne False quando a resposta do destinatário indicar com clareza que ele(a) não é quem a empresa está tentando contactar ou se ele(a) expressar o desejo de não ##receber mais mensagens, como ao responder "SAIR" (considere erros de digitação).

                    #Mensagem recebida: "{data}"

                    """
    headers = {"Content-Type": "application/json"}

    response = requests.request("POST", url,    json={
            "model": "gemma3",
            "prompt": prompt,
            "stream": False
        })
    
   
    content_response = json.loads(response.text)
    
    return (
        content_response['response']
        if content_response['response']
        else False
    )


verificar_contatos = []
try:

    pg = db_connect()
    pg.conectar()
    cursor = pg.conn.cursor()
    query = "SELECT sender_id, message_content from message_history where message_content <> '' and message_content <> 'Resposta automática';"

    cursor.execute(query)
    resultados = cursor.fetchall()

    for resultado in tqdm(resultados, desc="processando messagens", colour='GREEN'):
        result = agente_verificador(whatsapp=resultado[0], message=resultado[1])
        vars = (resultado[0], result, resultado[1])
        pg.cursor.execute(
            f"""
            INSERT INTO public.verifica_whatsapp(
	        telefone, validado, message_content)
	        VALUES (%s, %s, %s);                        
        """,
            vars,
        )
        pg.conn.commit()
    pg.desconectar()
except Exception as e:
    print(e)
