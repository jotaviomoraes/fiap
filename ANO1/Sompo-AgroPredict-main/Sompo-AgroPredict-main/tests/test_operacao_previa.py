"""Reexecucoes da telemetria reutilizam somente uma previa ainda valida."""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import apoio

sys.path.insert(0, str(apoio.RAIZ / "src" / "dashboard"))

from agropredict.entrada import LeituraInvalida
from paginas import operacao


class PreviaOperacaoTests(unittest.TestCase):
    def setUp(self):
        self.ctx = SimpleNamespace(servico=Mock(modelo=object()))
        self.sessao = {}
        self.patch_sessao = patch.object(operacao.st, "session_state", self.sessao)
        self.patch_sessao.start()
        self.addCleanup(self.patch_sessao.stop)

    def test_rerun_sem_mudanca_nao_repete_inferencia(self):
        primeira = operacao._avaliar_previa(self.ctx, apoio.LEITURA_SEGURA)
        segunda = operacao._avaliar_previa(self.ctx, dict(apoio.LEITURA_SEGURA))
        self.assertIs(primeira, segunda)
        self.ctx.servico.avaliar.assert_called_once()

    def test_mudanca_de_leitura_ou_modelo_recalcula(self):
        operacao._avaliar_previa(self.ctx, apoio.LEITURA_SEGURA)
        operacao._avaliar_previa(self.ctx, apoio.LEITURA_CRITICA)
        self.ctx.servico.modelo = object()
        operacao._avaliar_previa(self.ctx, apoio.LEITURA_CRITICA)
        self.assertEqual(self.ctx.servico.avaliar.call_count, 3)

    def test_entrada_invalida_nao_reutiliza_previa_anterior(self):
        operacao._avaliar_previa(self.ctx, apoio.LEITURA_SEGURA)
        with self.assertRaises(LeituraInvalida):
            operacao._avaliar_previa(self.ctx, {**apoio.LEITURA_SEGURA, "velocidade": None})
        self.ctx.servico.avaliar.assert_called_once()

    def test_falha_de_avaliacao_nao_fica_em_cache(self):
        self.ctx.servico.avaliar.side_effect = [RuntimeError("falha temporaria"), object()]
        with self.assertRaises(RuntimeError):
            operacao._avaliar_previa(self.ctx, apoio.LEITURA_SEGURA)
        self.assertNotIn("_previa_operacao", self.sessao)
        operacao._avaliar_previa(self.ctx, apoio.LEITURA_SEGURA)
        self.assertEqual(self.ctx.servico.avaliar.call_count, 2)
