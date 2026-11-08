"""Monta os servicos do sistema a partir da configuracao (usado pela UI e pelos scripts)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .config import DB_PATH, MODELO_PATH, backend_configurado, config_oracle, configurar_logging
from .modelo import ModeloRisco
from .persistencia import RepositorioSQLite
from .relatorios import Relatorios
from .seguranca import ServicoAutenticacao
from .servico import ServicoAvaliacao

logger = logging.getLogger("agropredict.fabrica")


@dataclass(frozen=True)
class Contexto:
    repo: object
    servico: ServicoAvaliacao
    auth: ServicoAutenticacao
    relatorios: Relatorios
    backend: str = "sqlite"
    aviso: str | None = None


def abrir_repositorio(backend: str | None = None, db_path: Path | str = DB_PATH):
    """Abre o repositorio pedido, com fallback automatico para SQLite.

    Retorna `(repo, backend_usado, aviso)`. Com `DB_BACKEND=oracle`, a
    indisponibilidade do Oracle gera excecao; com `auto` (padrao), cai
    para o SQLite e devolve o motivo em `aviso`.
    """
    backend = (backend or backend_configurado()).lower()
    if backend not in ("auto", "oracle", "sqlite"):
        backend = "auto"

    if backend == "sqlite":
        return RepositorioSQLite(db_path), "sqlite", None

    from .repositorio_oracle import RepositorioOracle, configurado as oracle_configurado

    config = config_oracle()
    if not oracle_configurado(config):
        if backend == "oracle":
            raise RuntimeError(
                "DB_BACKEND=oracle, mas ORACLE_USER/ORACLE_PASSWORD/ORACLE_DSN nao estao definidos "
                "em config/.env."
            )
        return RepositorioSQLite(db_path), "sqlite", "Oracle nao configurado (credenciais ausentes)."

    try:
        return RepositorioOracle(config), "oracle", None
    except Exception as exc:
        if backend == "oracle":
            raise RuntimeError(f"Falha ao conectar ao Oracle: {exc}") from exc
        logger.warning("Oracle indisponivel, usando SQLite: %s", exc)
        return RepositorioSQLite(db_path), "sqlite", f"Oracle indisponivel: {exc}"


def criar_contexto(db_path: Path | str = DB_PATH, modelo_path: Path | str = MODELO_PATH,
                   com_oracle: bool = True, backend: str | None = None) -> Contexto:
    repo, backend_usado, aviso = abrir_repositorio(backend, db_path)
    # O log fica ao lado do banco usado: execucoes com banco temporario nao escrevem no projeto
    if backend_usado == "oracle":
        configurar_logging(Path(db_path).parent / "agropredict.log")
    else:
        configurar_logging(Path(db_path).parent / "agropredict.log")
    modelo = ModeloRisco.carregar(Path(modelo_path))
    # Oracle como banco principal nao precisa de replicacao. O SQLite
    # explicito (dev/testes) ainda pode replicar, se configurado.
    replicar = config_oracle() if (com_oracle and backend_usado == "sqlite"
                                   and (backend or backend_configurado()) == "sqlite") else None
    servico = ServicoAvaliacao(repo, modelo, replicar)
    return Contexto(repo, servico, ServicoAutenticacao(repo), Relatorios(repo), backend_usado, aviso)


def criar_repositorio(backend: str | None = None, db_path: Path | str = DB_PATH):
    """Atalho para scripts que so precisam do banco (sem carregar o modelo)."""
    repo, backend_usado, aviso = abrir_repositorio(backend, db_path)
    configurar_logging(Path(db_path).parent / "agropredict.log")
    if aviso:
        logger.warning(aviso)
    return repo, backend_usado, aviso
