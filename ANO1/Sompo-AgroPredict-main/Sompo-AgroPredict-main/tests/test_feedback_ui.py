"""Classificador Streamlit com os pesos reais da BiLSTM do notebook RNN."""
import os
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]


class FeedbackUITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.codigo = f'''
import sys
sys.path.insert(0, {str(RAIZ / "src")!r})
sys.path.insert(0, {str(RAIZ / "src/dashboard")!r})
import streamlit as st
from agropredict.seguranca import Sessao
st.session_state["idioma"] = "pt"
st.session_state["sessao"] = Sessao("operador-ui", "operador")
from paginas.feedback import render
render()
'''

    def app(self):
        return AppTest.from_string(self.codigo).run(timeout=30)

    def test_modelo_ausente_desabilita_analise(self):
        with patch.dict(os.environ, {"FEEDBACK_MODELO": str(Path(self.tmp.name) / "ausente.pt")}):
            app = self.app()
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(app.button[0].disabled)
            self.assertTrue(any("indisponível" in s.value for s in app.error))

    def test_idioma_do_texto_independe_do_idioma_da_interface(self):
        with patch.dict(os.environ, {"FEEDBACK_MODELO": str(Path(self.tmp.name) / "ausente.pt")}):
            codigo = self.codigo.replace('st.session_state["idioma"] = "pt"',
                                         'st.session_state["idioma"] = "en"')
            app = AppTest.from_string(codigo).run(timeout=30)
            self.assertEqual(app.selectbox[0].value, "pt")
            self.assertEqual(app.title[0].value, "o que achou dessa aplicacao ?")

    @unittest.skipUnless(importlib.util.find_spec("torch"), "Requer o ambiente PyTorch")
    def test_classifica_bom_e_ruim_sem_nota_manual(self):
        with patch.dict(os.environ, {"FEEDBACK_MODELO": str(RAIZ / "src/modelo/feedback_bilstm.pt")}):
            app = self.app()
            self.assertEqual(len(app.radio), 0)
            self.assertEqual(len(app.selectbox), 1)
            self.assertEqual(app.selectbox[0].value, "pt")
            self.assertEqual(app.title[0].value, "o que achou dessa aplicacao ?")
            for texto, classe in [("Gostei muito do projeto, excelente e fácil de usar.", "BOM"),
                                  ("Não gostei, o sistema é ruim e muito lento.", "RUIM"),
                                  ("O mapa ajuda, mas os alertas poderiam ser mais claros.", "RUIM")]:
                app.text_area[0].set_value(texto)
                app.button[0].click().run(timeout=30)
                self.assertEqual(len(app.exception), 0)
                self.assertTrue(any(s.value.startswith(classe + " —") for s in [*app.success, *app.error]))
                self.assertEqual(len(app.get("image")), 1)
                self.assertTrue(any(s.value == "Raio-X das palavras" for s in app.subheader))
                self.assertTrue(any("ΔP=" in s.value for s in app.markdown))
                self.assertEqual(len(app.text_area), 2)
                self.assertTrue(app.text_area[1].disabled)
                self.assertIn("BiLSTM B2W", app.text_area[1].value)
                self.assertIn("Palavras mais decisivas:", app.text_area[1].value)

    @unittest.skipUnless(importlib.util.find_spec("torch"), "Requer o ambiente PyTorch")
    def test_ingles_e_troca_de_idioma(self):
        with patch.dict(os.environ, {"FEEDBACK_MODELO_EN": str(RAIZ / "src/modelo/feedback_bilstm_en.pt")}):
            app = self.app()
            app.selectbox[0].set_value("en").run(timeout=30)
            for texto, classe in [("This is an excellent wonderful application, I love it.", "BOM"),
                                  ("This is terrible, boring and a complete waste of time.", "RUIM")]:
                app.text_area[0].set_value(texto)
                app.button[0].click().run(timeout=30)
                self.assertEqual(len(app.exception), 0)
                self.assertTrue(any(s.value.startswith(classe + " —") for s in [*app.success, *app.error]))
                self.assertIn("BiLSTM IMDB", app.text_area[1].value)
                self.assertEqual(len(app.get("image")), 1)
            app.selectbox[0].set_value("pt").run(timeout=30)
            self.assertNotIn("sentimento_resultado", app.session_state)
            self.assertFalse(app.success)
            self.assertEqual(len(app.text_area), 1)

    @unittest.skipUnless(importlib.util.find_spec("torch"), "Requer o ambiente PyTorch")
    def test_modelo_ingles_ausente_nao_utiliza_portugues(self):
        with patch.dict(os.environ, {"FEEDBACK_MODELO_EN": str(Path(self.tmp.name) / "ausente-en.pt")}):
            app = self.app()
            app.selectbox[0].set_value("en").run(timeout=30)
            self.assertTrue(app.button[0].disabled)
            self.assertTrue(any("indisponível" in s.value for s in app.error))

    @unittest.skipUnless(importlib.util.find_spec("torch"), "Requer o ambiente PyTorch")
    def test_texto_vazio_e_resultado_antigo(self):
        with patch.dict(os.environ, {"FEEDBACK_MODELO": str(RAIZ / "src/modelo/feedback_bilstm.pt")}):
            app = self.app()
            app.button[0].click().run(timeout=30)
            self.assertTrue(app.warning)
            app.text_area[0].set_value("Produto excelente, gostei muito.")
            app.button[0].click().run(timeout=30)
            self.assertTrue(app.success)
            app.text_area[0].set_value("Produto ruim, não gostei.").run(timeout=30)
            self.assertFalse(app.success)
            self.assertFalse(app.error)


if __name__ == "__main__":
    unittest.main()
