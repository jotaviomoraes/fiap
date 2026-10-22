"""Inicializacao da demonstracao sem substituir dados existentes."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import apoio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.simular_frota import popular_demonstracao, simular_frota


class DemonstracaoTests(unittest.TestCase):
    def test_banco_vazio_chama_simulador(self):
        with apoio.BancoTemporario() as b:
            ctx = SimpleNamespace(repo=b.repo, servico=b.servico)
            with patch("scripts.simular_frota.simular_frota", return_value=123) as simular:
                self.assertEqual(popular_demonstracao(ctx), 123)
                simular.assert_called_once_with(ctx)

    def test_banco_com_leitura_nao_e_alterado(self):
        with apoio.BancoTemporario() as b:
            b.servico.registrar_leitura(apoio.LEITURA_SEGURA, 1, "op.teste")
            ctx = SimpleNamespace(repo=b.repo, servico=b.servico)
            with patch("scripts.simular_frota.simular_frota") as simular:
                self.assertEqual(popular_demonstracao(ctx), 0)
                simular.assert_not_called()
            self.assertEqual(len(b.repo.consultar("SELECT * FROM leituras")), 1)

    def test_simulacao_gera_predicoes_e_nao_repete_bootstrap(self):
        with apoio.BancoTemporario() as b:
            ctx = SimpleNamespace(repo=b.repo, servico=b.servico)
            total = simular_frota(ctx, dias=2, leituras_por_dia=1, taxa_falhas=0)
            self.assertGreater(total, 0)
            self.assertEqual(len(b.repo.consultar("SELECT * FROM predicoes")), total)
            self.assertEqual(popular_demonstracao(ctx), 0)
            self.assertEqual(len(b.repo.consultar("SELECT * FROM predicoes")), total)
