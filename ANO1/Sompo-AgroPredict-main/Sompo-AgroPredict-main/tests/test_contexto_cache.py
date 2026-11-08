"""O contexto deve trocar o modelo em memoria quando codigo ou artefatos mudam."""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import apoio

sys.path.insert(0, str(apoio.RAIZ / "src" / "dashboard"))
import ui_comum


class CacheContextoTests(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.codigo, self.modelo, self.meta = [Path(pasta.name) / n for n in ("modelo.py", "modelo.pkl", "meta.json")]
        for arquivo in (self.codigo, self.modelo, self.meta):
            arquivo.write_bytes(b"inicial")
        patches = (
            patch.object(ui_comum, "modulo_modelo", SimpleNamespace(__file__=str(self.codigo))),
            patch.object(ui_comum, "MODELO_PATH", self.modelo),
            patch.object(ui_comum, "MODELO_META_PATH", self.meta),
        )
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        ui_comum._contexto_cache.clear()
        self.addCleanup(ui_comum._contexto_cache.clear)

    def test_reutiliza_contexto_sem_mudancas(self):
        with patch.object(ui_comum, "criar_contexto", side_effect=lambda: object()) as criar:
            primeiro = ui_comum.contexto()
            self.assertIs(ui_comum.contexto(), primeiro)
            criar.assert_called_once()

    def test_mudanca_de_codigo_modelo_ou_meta_reconstroi_contexto(self):
        with patch.object(ui_comum, "criar_contexto", side_effect=lambda: object()) as criar:
            anterior = ui_comum.contexto()
            for arquivo in (self.codigo, self.modelo, self.meta):
                arquivo.write_bytes(b"nova versao")
                atual = ui_comum.contexto()
                self.assertIsNot(atual, anterior)
                anterior = atual
            self.assertEqual(criar.call_count, 4)
