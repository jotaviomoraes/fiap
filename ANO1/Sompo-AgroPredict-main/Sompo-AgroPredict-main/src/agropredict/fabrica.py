"""Monta os servicos do sistema a partir da configuracao (usado pela UI e pelos scripts)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import DB_PATH, MODELO_PATH, config_oracle, configurar_logging
from .modelo import ModeloRisco
from .persistencia import RepositorioSQLite
from .relatorios import Relatorios
from .seguranca import ServicoAutenticacao
from .servico import ServicoAvaliacao


@dataclass(frozen=True)
class Contexto:
    repo: RepositorioSQLite
    servico: ServicoAvaliacao
    auth: ServicoAutenticacao
    relatorios: Relatorios


def criar_contexto(db_path: Path | str = DB_PATH, modelo_path: Path | str = MODELO_PATH,
                   com_oracle: bool = True) -> Contexto:
    # O log fica ao lado do banco usado: execucoes com banco temporario nao escrevem no projeto
    configurar_logging(Path(db_path).parent / "agropredict.log")
    repo = RepositorioSQLite(db_path)
    modelo = ModeloRisco.carregar(Path(modelo_path))
    servico = ServicoAvaliacao(repo, modelo, config_oracle() if com_oracle else None)
    return Contexto(repo, servico, ServicoAutenticacao(repo), Relatorios(repo))
