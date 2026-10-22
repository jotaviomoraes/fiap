"""Pipeline de qualidade: inconsistencias, faltantes e duplicidades antes do modelo."""

import unittest

import numpy as np
import pandas as pd

import apoio  # noqa: F401

from agropredict.qualidade import converter_numero, limpar_dataset, normalizar_classe, normalizar_status

LINHA = {"umidade_solo": 20.0, "declividade": 5.0, "chuva_24h": 2.0, "temperatura": 25.0, "velocidade": 6.0,
         "idade_maquina": 3.0, "horas_operacao": 3.0, "status_operacao": "Colheita", "risco": "BAIXO"}


def _etapa(relatorio, trecho):
    return next(e["afetados"] for e in relatorio.etapas if trecho in e["etapa"])


class NormalizacaoTests(unittest.TestCase):
    def test_numero(self):
        self.assertEqual(converter_numero("12,5"), 12.5)
        self.assertEqual(converter_numero(" 7.25 "), 7.25)
        self.assertTrue(np.isnan(converter_numero("N/A")))
        self.assertTrue(np.isnan(converter_numero(float("inf"))))

    def test_status_e_classe(self):
        self.assertEqual(normalizar_status("  COLHEITA "), "Colheita")
        self.assertTrue(pd.isna(normalizar_status("Plantio")))
        self.assertEqual(normalizar_classe("Médio"), "MEDIO")
        self.assertTrue(pd.isna(normalizar_classe("CRITICO")))


class LimpezaTests(unittest.TestCase):
    def test_trata_cada_tipo_de_problema(self):
        bruto = pd.DataFrame([
            LINHA,
            {**LINHA, "velocidade": "7,5", "status_operacao": " manobra"},     # texto decimal + grafia
            {**LINHA, "umidade_solo": 180.0},                                 # sensor impossivel
            {**LINHA, "temperatura": "erro"},                                 # nao numerico
            {**LINHA, "risco": None},                                         # sem rotulo
            {**LINHA, "risco": "alto", "chuva_24h": 50.0},                     # rotulo com outra grafia
            LINHA,                                                            # duplicata exata
            {**LINHA, "chuva_24h": 9.0, "risco": "BAIXO"},
            {**LINHA, "chuva_24h": 9.0, "risco": "MEDIO"},                     # conflito
            {**LINHA, "umidade_solo": None, "declividade": None, "chuva_24h": None},  # 3 faltantes
        ])
        limpo, rel = limpar_dataset(bruto)

        self.assertEqual(_etapa(rel, "texto"), 1)
        self.assertEqual(_etapa(rel, "não numérico"), 1)
        self.assertEqual(_etapa(rel, "grafia inconsistente"), 1)
        self.assertEqual(_etapa(rel, "impossível"), 1)
        self.assertEqual(_etapa(rel, "Sem rótulo"), 1)
        self.assertEqual(_etapa(rel, "Rótulo com grafia"), 1)
        self.assertEqual(_etapa(rel, "Duplicata exata"), 1)
        self.assertEqual(_etapa(rel, "rótulos diferentes"), 2)
        self.assertEqual(_etapa(rel, "faltantes"), 1)

        self.assertEqual(len(limpo), 5)
        self.assertEqual(rel.linhas_saida, 5)
        self.assertEqual(rel.faltantes_restantes, {"umidade_solo": 1, "temperatura": 1})
        self.assertIn(7.5, limpo["velocidade"].tolist())
        self.assertIn("Manobra", limpo["status_operacao"].tolist())
        self.assertIn("ALTO", limpo["risco"].tolist())
        self.assertFalse(limpo.duplicated().any())

    def test_colunas_obrigatorias(self):
        with self.assertRaises(ValueError):
            limpar_dataset(pd.DataFrame([{"umidade_solo": 1}]))

    def test_dataset_versionado_fica_apto(self):
        bruto = pd.read_csv(apoio.RAIZ / "src" / "data" / "dataset_v3_bruto.csv")
        limpo, rel = limpar_dataset(bruto)
        self.assertGreater(rel.linhas_saida, 0.9 * rel.linhas_entrada)
        self.assertFalse(limpo.duplicated().any())
        self.assertTrue(set(limpo["risco"]) <= {"BAIXO", "MEDIO", "ALTO"})
        for coluna in ("umidade_solo", "velocidade", "temperatura"):
            self.assertTrue(limpo[coluna].dropna().between(-10, 100).all())


if __name__ == "__main__":
    unittest.main()
