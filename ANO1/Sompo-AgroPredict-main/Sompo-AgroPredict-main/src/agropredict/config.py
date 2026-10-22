"""Configuracao central: caminhos, versao do modelo e logging."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[2]

MODELO_PATH = RAIZ_PROJETO / "src" / "modelo" / "modelo.pkl"
MODELO_META_PATH = RAIZ_PROJETO / "src" / "modelo" / "modelo_meta.json"
# Versao usada apenas quando o modelo nao tem metadados (modelo legado)
VERSAO_MODELO = "v1.0"

# Banco e logs sao gerados em runtime e ficam fora do versionamento.
DATA_DIR = Path(os.getenv("AGROPREDICT_DATA_DIR", RAIZ_PROJETO / "data"))
DB_PATH = Path(os.getenv("AGROPREDICT_DB", DATA_DIR / "agropredict.db"))
LOG_PATH = DATA_DIR / "agropredict.log"


def config_oracle() -> dict:
    """Credenciais do Oracle opcional, sempre lidas do ambiente."""
    return {
        "user": os.getenv("ORACLE_USER"),
        "password": os.getenv("ORACLE_PASSWORD"),
        "dsn": os.getenv("ORACLE_DSN"),
    }


def configurar_logging(caminho: Path = LOG_PATH, nivel: int = logging.INFO) -> logging.Logger:
    """Configura o logger `agropredict` com arquivo rotativo (idempotente)."""
    logger = logging.getLogger("agropredict")
    if logger.handlers:
        return logger

    logger.setLevel(nivel)
    formato = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(caminho, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    except OSError:
        handler = logging.StreamHandler()
    handler.setFormatter(formato)
    logger.addHandler(handler)
    return logger


def encerrar_logging() -> None:
    """Fecha o arquivo de log (necessario no Windows antes de apagar a pasta do banco)."""
    logger = logging.getLogger("agropredict")
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
