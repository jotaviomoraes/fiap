"""Configuracao central: caminhos, backend do banco, versao do modelo e logging."""

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

# ---------------------------------------------------------------------
# Variaveis de ambiente
# ---------------------------------------------------------------------
# `config/.env` tem prioridade e nao e versionado. O `.env` da raiz do
# projeto/workspace tambem e aceito para compatibilidade com setups antigos.
CANDIDATOS_ENV = (
    RAIZ_PROJETO / "config" / ".env",
    RAIZ_PROJETO / ".env",
    RAIZ_PROJETO.parent / ".env",
)


def carregar_env() -> None:
    """Carrega os arquivos .env sem sobrescrever variaveis ja definidas no SO."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dependencia opcional
        _carregar_env_simples()
        return
    for caminho in CANDIDATOS_ENV:
        if caminho.is_file():
            load_dotenv(caminho, override=False, encoding="utf-8")


def _carregar_env_simples() -> None:
    """Fallback minimo quando python-dotenv nao esta instalado."""
    for caminho in CANDIDATOS_ENV:
        if not caminho.is_file():
            continue
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, valor = linha.split("=", 1)
            valor = valor.strip().strip("'\"")
            os.environ.setdefault(chave.strip(), valor)


carregar_env()

# Banco e logs sao gerados em runtime e ficam fora do versionamento.
DATA_DIR = Path(os.getenv("AGROPREDICT_DATA_DIR", RAIZ_PROJETO / "data"))
DB_PATH = Path(os.getenv("AGROPREDICT_DB", DATA_DIR / "agropredict.db"))
LOG_PATH = DATA_DIR / "agropredict.log"

BACKENDS_VALIDOS = ("auto", "oracle", "sqlite")
BACKEND_PADRAO = (os.getenv("DB_BACKEND") or "auto").strip().lower()
if BACKEND_PADRAO not in BACKENDS_VALIDOS:
    BACKEND_PADRAO = "auto"


def backend_configurado() -> str:
    """Backend pedido pela configuracao: auto, oracle ou sqlite."""
    return BACKEND_PADRAO


def config_oracle() -> dict:
    """Parametros de conexao com o Oracle Autonomous Database (modo Thin).

    A wallet e passada explicitamente (`config_dir` e `wallet_location`)
    porque o `sqlnet.ora` da wallet costuma apontar para `?/network/admin`.
    Assim nao e necessario Oracle Instant Client nem TNS_ADMIN global.
    """
    config: dict = {
        "user": (os.getenv("ORACLE_USER") or "").strip(),
        "password": os.getenv("ORACLE_PASSWORD") or "",
        "dsn": (os.getenv("ORACLE_DSN") or "joaopersonal_tp").strip(),
    }
    config_dir = (os.getenv("ORACLE_CONFIG_DIR") or "").strip()
    wallet_location = (os.getenv("ORACLE_WALLET_LOCATION") or "").strip()
    wallet_password = os.getenv("ORACLE_WALLET_PASSWORD") or ""
    if config_dir:
        config["config_dir"] = config_dir
    if wallet_location:
        config["wallet_location"] = wallet_location
    if wallet_password:
        config["wallet_password"] = wallet_password
    return config


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
