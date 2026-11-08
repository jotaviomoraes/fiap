"""DDL Oracle deve rodar apenas na preparacao explicita do banco."""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import apoio

from agropredict.repositorio_oracle import RepositorioOracle


class SchemaOracleTests(unittest.TestCase):
    def test_conexao_do_app_nao_executa_ddl(self):
        config = {"user": "teste", "password": "teste", "dsn": "teste"}
        with patch.dict(sys.modules, {"oracledb": SimpleNamespace()}), \
                patch.object(RepositorioOracle, "_obter_pool"), \
                patch.object(RepositorioOracle, "inicializar") as inicializar:
            RepositorioOracle(config)
            inicializar.assert_not_called()

    def test_preparacao_explicita_executa_schema(self):
        config = {"user": "teste", "password": "teste", "dsn": "teste"}
        with patch.dict(sys.modules, {"oracledb": SimpleNamespace()}), \
                patch.object(RepositorioOracle, "_obter_pool"), \
                patch.object(RepositorioOracle, "inicializar") as inicializar:
            RepositorioOracle(config, criar_schema=True)
            inicializar.assert_called_once_with()
