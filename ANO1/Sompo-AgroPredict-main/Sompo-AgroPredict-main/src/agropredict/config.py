"""Configuracao central: caminhos, backend do banco, versao do modelo e logging."""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from functools import lru_cache
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock

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


def _valor_config(nome: str, padrao: str = "") -> str:
    """Ambiente/.env primeiro; Secrets TOML na raiz quando executado pelo Streamlit."""
    valor = os.getenv(nome)
    if valor is None:
        streamlit = sys.modules.get("streamlit")
        if streamlit is not None:
            try:
                valor = streamlit.secrets.get(nome)
            except FileNotFoundError:
                pass  # CLI e desenvolvimento sem secrets.toml continuam funcionando.
            except Exception:
                raise ValueError("Nao foi possivel ler os Secrets do Streamlit. Verifique o formato TOML.") from None
    if valor is None:
        return padrao
    if not isinstance(valor, str):
        raise ValueError(f"{nome} deve ser texto nos Secrets.")
    return valor


_LOCK_WALLET = Lock()


@lru_cache(maxsize=None)
def _criar_wallet_temporaria(tnsnames: str, pem: str) -> tempfile.TemporaryDirectory:
    """O cache mantém a pasta viva até o fim do processo; nada é salvo no projeto."""
    pasta = tempfile.TemporaryDirectory(prefix="agropredict-wallet-")
    try:
        for nome, conteudo in (("tnsnames.ora", tnsnames), ("ewallet.pem", pem)):
            caminho = Path(pasta.name) / nome
            # mkdtemp usa 0700 no Linux; os arquivos recebem 0600 na criação.
            descritor = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descritor, "w", encoding="utf-8", newline="\n") as arquivo:
                arquivo.write(conteudo)
    except OSError:
        pasta.cleanup()
        raise RuntimeError("Nao foi possivel criar os arquivos temporarios da wallet Oracle.") from None
    return pasta


def _wallet_dos_secrets(tnsnames: str, pem: str) -> str | None:
    tnsnames = tnsnames.lstrip("\ufeff").replace("\r\n", "\n").strip()
    pem = pem.lstrip("\ufeff").replace("\r\n", "\n").strip()
    if not tnsnames and not pem:
        return None
    if not tnsnames or not pem:
        raise ValueError("Defina ORACLE_TNSNAMES e ORACLE_WALLET_PEM juntos, com o conteudo completo dos arquivos.")
    if "-----BEGIN " not in pem or "-----END " not in pem:
        raise ValueError("ORACLE_WALLET_PEM deve conter o arquivo PEM completo, incluindo BEGIN e END.")
    # Evita duas pastas simultâneas em sessões que abrem a primeira conexão juntas.
    with _LOCK_WALLET:
        return _criar_wallet_temporaria(tnsnames + "\n", pem + "\n").name


def backend_configurado() -> str:
    """Backend pedido pela configuracao: auto, oracle ou sqlite."""
    backend = _valor_config("DB_BACKEND", BACKEND_PADRAO).strip().lower()
    return backend if backend in BACKENDS_VALIDOS else "auto"


def config_oracle() -> dict:
    """Parametros de conexao com o Oracle Autonomous Database (modo Thin).

    A wallet e passada explicitamente (`config_dir` e `wallet_location`)
    porque o `sqlnet.ora` da wallet costuma apontar para `?/network/admin`.
    Assim nao e necessario Oracle Instant Client nem TNS_ADMIN global.
    ORACLE_TNSNAMES e ORACLE_WALLET_PEM juntos recriam a wallet temporaria
    a partir do ambiente ou dos Secrets; sem eles, os caminhos locais permanecem.
    """
    config: dict = {
        "user": _valor_config("ORACLE_USER").strip(),
        "password": _valor_config("ORACLE_PASSWORD"),
        "dsn": (_valor_config("ORACLE_DSN") or "joaopersonal_tp").strip(),
    }
    config_dir = _valor_config("ORACLE_CONFIG_DIR").strip()
    wallet_location = _valor_config("ORACLE_WALLET_LOCATION").strip()
    wallet_password = _valor_config("ORACLE_WALLET_PASSWORD")
    pasta_secrets = _wallet_dos_secrets(_valor_config("ORACLE_TNSNAMES"), _valor_config("ORACLE_WALLET_PEM"))
    if pasta_secrets:
        # Conteúdos explícitos substituem caminhos de outra máquina (ex.: Windows).
        config_dir = wallet_location = pasta_secrets
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
