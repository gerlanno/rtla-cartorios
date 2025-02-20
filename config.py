import os
import os
import pprint
from dotenv import load_dotenv
import psycopg2
from utils.logger import Logger

logger = Logger().get_logger()


load_dotenv()

# nome do cartorio e código do cartorio
PRIMEIRO_CARTORIO_DE_FORTALEZA = "1"
OSIAN_ARARIPE = "5"
CARTORIO_AGUIAR = "8"

db_config = {
    "host": "localhost",
    "database": "dbsender",
    "user": "postgres",
    "password": os.getenv("DB_PG_PASS"),
}



wa_config = {
    "OSIAN1": {
        "NOME": "OSIAN ARARIPE",
        "WA_TOKEN": os.getenv("OSIAN_TOKEN"),
        "PHONE_NUMBER_ID": os.getenv(
            "OSIAN1_PHONE_NUMBER_ID"
        ),  # "display_phone_number": "+55 85 8663-3919"
    },
    "OSIAN2": {
        "NOME": "OSIAN ARARIPE",
        "WA_TOKEN": os.getenv("OSIAN_TOKEN"),
        "PHONE_NUMBER_ID": os.getenv(
            "OSIAN2_PHONE_NUMBER_ID"
        ),  # "display_phone_number": "+55 85 8663-2161"
    },
    "AGUIAR1": {
        "NOME": "CARTORIO AGUIAR",
        "WA_TOKEN": os.getenv("AGUIAR_TOKEN"),
        "PHONE_NUMBER_ID": os.getenv(
            "AGUIAR1_PHONE_NUMBER_ID"
        ),  # "display_phone_number": "+55 85 9759-0064"
    },
    "AGUIAR2": {
        "NOME": "CARTORIO AGUIAR",
        "WA_TOKEN": os.getenv("AGUIAR_TOKEN"),
        "PHONE_NUMBER_ID": os.getenv(
            "AGUIAR2_PHONE_NUMBER_ID"
        ),  # "display_phone_number": "+55 85 9412-9614"
    },
    "IEPTBCE1": {
        "NOME": "Instituto de Cartórios de Protestos do Ceará - IEPTBCE",
        "WA_TOKEN": os.getenv("IEPTBCE_TOKEN"),
        "PHONE_NUMBER_ID": os.getenv(
            "IEPTBCE1_PHONE_NUMBER_ID"
        ),  # "display_phone_number": "+55 85 9841-1019"
    },
    "IEPTBCE2": {
        "NOME": "Instituto de Cartórios de Protestos do Ceará - IEPTBCE",
        "WA_TOKEN": os.getenv("IEPTBCE_TOKEN"),
        "PHONE_NUMBER_ID": os.getenv(
            "IEPTBCE2_PHONE_NUMBER_ID"
        ),  # "display_phone_number": "+55 85 8217-5611"
    },
    "IEPTBCE3": {
        "NOME": "Instituto de Cartórios de Protestos do Ceará - IEPTBCE",
        "WA_TOKEN": os.getenv("IEPTBCE_TOKEN"),
        "PHONE_NUMBER_ID": os.getenv(
            "IEPTBCE3_PHONE_NUMBER_ID"
        ),  # "display_phone_number": "+55 85 9936-6186"
    },
    "RTLA1": {
        "NOME": "Instituto de Cartórios de Protestos do Ceará - IEPTBCE",
        "WA_TOKEN": os.getenv("RTLA_TOKEN"),
        "PHONE_NUMBER_ID": os.getenv(
            "RTLA1_PHONE_NUMBER_ID"
        ),  # "display_phone_number": "+55 85 9841-1242"
    },
    "RTLA2": {
        "NOME": "Instituto de Cartórios de Protestos do Ceará - IEPTBCE",
        "WA_TOKEN": os.getenv("RTLA_TOKEN"),
        "PHONE_NUMBER_ID": os.getenv(
            "RTLA2_PHONE_NUMBER_ID"
        ),  # "display_phone_number": "+55 85 9841-1052"
    },
}


def find_token(phone_number_id):
    for item in wa_config.values():
        if item.get("PHONE_NUMBER_ID") == phone_number_id:

            token_found = item.get("WA_TOKEN")

            break
        else:
            token_found = ""
    return token_found if token_found else print("Token não localizado")


class Config:
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///users.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False



class ConexaoDB:
    def __init__(self, db_host, db_name, db_user, db_pass):
        self.db_host = db_host
        self.db_name = db_name
        self.db_user = db_user
        self.db_pass = db_pass
        self.conn = None
        self.cursor = None

    def conectar(self):
        try:
            self.conn = psycopg2.connect(
                host=self.db_host,
                database=self.db_name,
                user=self.db_user,
                password=self.db_pass,
            )
            self.cursor = self.conn.cursor()
            
        except Exception as e:
            logger.error(f"Erro ao conectar com banco de dados: {e}")

    def desconectar(self):
        if self.cursor is not None:
            self.cursor.close()
        if self.conn is not None:
            self.conn.close()
           


def db_connect():
    pg = ConexaoDB(
        db_config.get("host"),
        db_config.get("database"),
        db_config.get("user"),
        db_config.get("password"),
    )
    return pg
