import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
import inspect
import stat

class Logger:
    def __init__(self):
        self.diretorio_raiz = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))
        self.log_directory = os.path.join(self.diretorio_raiz, "logs")

        if not os.path.exists(self.log_directory):
            os.makedirs(self.log_directory, exist_ok=True)
            os.chmod(self.log_directory, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        self.handler = None
        self.update_log_file()

    def update_log_file(self):
        """Atualiza o arquivo de log diariamente"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.log_directory, f"{current_date}.log")

       
        if self.handler:
            self.logger.removeHandler(self.handler)

        # Criar novo handler para o arquivo do dia
        self.handler = TimedRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=7)
        self.handler.suffix = "%Y-%m-%d"

        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s - Script: %(filename)s")
        self.handler.setFormatter(formatter)

        self.logger.addHandler(self.handler)

    def get_logger(self):
        """Garante que o log está atualizado diariamente"""
        self.update_log_file()
        return self.logger
