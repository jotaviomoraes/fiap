"""Utilidades compartilhadas pelos testes: caminho do pacote e banco temporario."""

import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from agropredict.modelo import ModeloRisco  # noqa: E402
from agropredict.persistencia import RepositorioSQLite  # noqa: E402
from agropredict.servico import ServicoAvaliacao  # noqa: E402

_MODELO = None

LEITURA_SEGURA = {
    "umidade_solo": 18, "declividade": 5, "chuva_24h": 2, "temperatura": 25,
    "velocidade": 6, "idade_maquina": 3, "horas_operacao": 3, "status_operacao": "Colheita",
}
LEITURA_CRITICA = {
    "umidade_solo": 60, "declividade": 22, "chuva_24h": 50, "temperatura": 39,
    "velocidade": 12, "idade_maquina": 15, "horas_operacao": 11, "status_operacao": "Manobra",
}


def modelo() -> ModeloRisco:
    global _MODELO
    if _MODELO is None:
        _MODELO = ModeloRisco.carregar()
    return _MODELO


class BancoTemporario:
    """Cria um SQLite isolado por teste e remove ao final."""

    def __enter__(self):
        self._dir = tempfile.TemporaryDirectory()
        self.repo = RepositorioSQLite(Path(self._dir.name) / "teste.db")
        self.servico = ServicoAvaliacao(self.repo, modelo(), config_oracle=None)
        return self

    def __exit__(self, *exc):
        self._dir.cleanup()
