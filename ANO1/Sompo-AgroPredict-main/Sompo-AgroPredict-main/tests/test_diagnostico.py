"""Integridade das avaliações e navegação dos sete diagnósticos disponíveis."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "src"), str(RAIZ / "src/dashboard")]

from agropredict.diagnostico import carregar_diagnostico, vencedor_risco
from agropredict.seguranca import PERFIS, Sessao
from streamlit.testing.v1 import AppTest


class DiagnosticoTests(unittest.TestCase):
    def test_selecao_depende_da_validacao_e_respeita_recall(self):
        candidatos = {
            "inseguro": {"recall_alto_cv": .94, "f1_macro_cv": .99},
            "melhor": {"recall_alto_cv": .95, "f1_macro_cv": .96},
            "outro": {"recall_alto_cv": .99, "f1_macro_cv": .92},
        }
        self.assertEqual(vencedor_risco(candidatos), "melhor")
        self.assertIsNone(vencedor_risco({"inseguro": candidatos["inseguro"]}))

    def test_procedencia_e_estagios_preservados(self):
        dados = carregar_diagnostico()
        self.assertEqual(dados["indisponiveis"], [])
        self.assertEqual(len(dados["modelos"]), 7)
        self.assertEqual(vencedor_risco(dados["risco"]["candidatos"]), "Gradient Boosting")
        modelos = {m["id"]: m for m in dados["modelos"]}
        self.assertEqual(modelos["risco_final"]["metricas"]["acuracia"], .9811)
        candidato = next(m for m in dados["modelos"] if m["nome"] == "Gradient Boosting")
        self.assertEqual(candidato["metricas"]["acuracia"], .9824)
        for m in dados["modelos"]:
            self.assertNotIn("r2", m["metricas"])
            matriz = m["metricas"].get("matriz_confusao")
            if matriz:
                self.assertEqual(sum(map(sum, matriz)), m["dataset"]["teste"])
        self.assertNotIn("baseline_majoritaria", modelos["sentimento_en"]["metricas"])
        self.assertNotIn("matriz_confusao", modelos["sentimento_pt"]["metricas"])

    def test_arquivos_ausentes_nao_inventam_metricas(self):
        with tempfile.TemporaryDirectory() as pasta:
            dados = carregar_diagnostico(Path(pasta))
        self.assertEqual(dados["modelos"], [])
        self.assertEqual(len(dados["indisponiveis"]), 3)

    def test_perfis_autenticados_podem_abrir(self):
        for perfil in PERFIS:
            self.assertTrue(Sessao("teste", perfil).pode("raio_x"))
        self.assertFalse(Sessao("teste", "desconhecido").pode("raio_x"))


class RaioXUITests(unittest.TestCase):
    def test_comparacao_sem_avaliacao_individual_nos_tres_idiomas(self):
        codigo = f"""
import sys
sys.path[:0] = [{str(RAIZ / 'src')!r}, {str(RAIZ / 'src/dashboard')!r}]
import streamlit as st
from agropredict.seguranca import Sessao
st.session_state['sessao'] = Sessao('teste', 'admin')
st.session_state['idioma'] = IDIOMA_TESTE
from paginas.raio_x import render
render()
"""
        from unittest.mock import patch
        with patch("agropredict.modelo.ModeloRisco.carregar", side_effect=AssertionError("Não carregar modelo")):
            for idioma in ("pt", "en", "es"):
                with patch("i18n.idioma_atual", return_value=idioma):
                    app = AppTest.from_string(codigo.replace("IDIOMA_TESTE", repr(idioma))).run(timeout=30)
                    self.assertFalse(app.exception, idioma)
                    self.assertEqual(len(app.selectbox), 0)
                    self.assertEqual(len(app.metric), 0)
                    graficos = app.get("vega_lite_chart")
                    self.assertEqual(len(graficos), 1)
                    spec = json.loads(graficos[0].proto.spec)
                    self.assertEqual(spec["encoding"]["y"]["scale"]["domain"], [80, 100])
                    self.assertEqual(spec["encoding"]["y"]["axis"]["values"], list(range(80, 101, 5)))
                    self.assertEqual(len(spec["encoding"]["color"]["scale"]["domain"]), 3)


if __name__ == "__main__":
    unittest.main()
