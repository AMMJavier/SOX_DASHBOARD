"""Conexión directa Oracle para consultas SQL existentes de controles SOX."""
import oracledb
from oracle_settings import get_oracle_config

class OracleConnection:
    def __init__(self):
        self._config = get_oracle_config()
        self.connection = None

    def connect(self):
        if self.connection is None:
            cfg = self._config
            dsn = oracledb.makedsn(cfg["host"], cfg["port"], service_name=cfg["service_name"])
            self.connection = oracledb.connect(user=cfg["user"], password=cfg["password"], dsn=dsn)
        return self.connection

    def close(self):
        if self.connection is not None:
            try:
                self.connection.close()
            finally:
                self.connection = None
