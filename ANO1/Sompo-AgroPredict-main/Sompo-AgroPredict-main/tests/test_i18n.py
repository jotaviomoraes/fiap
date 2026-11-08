"""Cobertura das traducoes EN/ES e formatacao por idioma do dashboard."""

import ast
import sys
import unittest
from pathlib import Path

import apoio

DASHBOARD = apoio.RAIZ / "src" / "dashboard"
sys.path.insert(0, str(DASHBOARD))

import i18n  # noqa: E402
from traducoes import CATALOGO  # noqa: E402


def _chaves_t() -> set[str]:
    """Todas as strings literais passadas para `t(...)` no dashboard."""
    chaves = set()
    for caminho in DASHBOARD.rglob("*.py"):
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if (isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
                    and no.func.id == "t" and no.args
                    and isinstance(no.args[0], ast.Constant)
                    and isinstance(no.args[0].value, str)):
                chaves.add(no.args[0].value)
    return chaves


class CatalogoTests(unittest.TestCase):
    def test_catalogo_sem_chaves_duplicadas(self):
        chaves = [pt for pt, _en, _es in CATALOGO]
        duplicadas = {c for c in chaves if chaves.count(c) > 1}
        self.assertEqual(duplicadas, set())

    def test_todo_texto_de_tela_tem_en_e_es(self):
        faltando = sorted(k for k in _chaves_t() if k not in i18n.TRADUCOES["en"])
        self.assertEqual(faltando, [], "string(ns) sem traducao EN/ES")

    def test_catalogo_nao_tem_traducao_vazia(self):
        vazias = [pt for pt, en, es in CATALOGO if not en.strip() or not es.strip()]
        self.assertEqual(vazias, [])


class TraducaoTests(unittest.TestCase):
    def setUp(self):
        self._original = i18n.idioma_atual

    def tearDown(self):
        i18n.idioma_atual = self._original

    def test_traduz_texto_e_interpola(self):
        i18n.idioma_atual = lambda: "en"
        self.assertEqual(i18n.t("Alertas"), "Alerts")
        self.assertEqual(
            i18n.t("{n} alerta(s)", n=3), "3 alert(s)"
        )
        i18n.idioma_atual = lambda: "es"
        self.assertEqual(i18n.t("Manutenção"), "Mantenimiento")

    def test_texto_sem_traducao_cai_para_portugues(self):
        i18n.idioma_atual = lambda: "en"
        self.assertEqual(i18n.t("Texto sem tradução"), "Texto sem tradução")

    def test_formatacao_de_numero_por_idioma(self):
        i18n.idioma_atual = lambda: "en"
        self.assertEqual(i18n.formatar_numero(1234.5, 1), "1,234.5")
        i18n.idioma_atual = lambda: "pt"
        self.assertEqual(i18n.formatar_numero(1234.5, 1), "1.234,5")


if __name__ == "__main__":
    unittest.main()
