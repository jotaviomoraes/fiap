import unittest

import apoio  # noqa: F401  (ajusta o sys.path)

from agropredict.regras import (
    calcular_score_risco,
    categorizar_alerta,
    gerar_recomendacao,
    verificar_max,
)


class CalcularScoreRiscoTests(unittest.TestCase):
    def test_baixo_com_alta_confianca_tem_score_baixo(self):
        score = calcular_score_risco(["ALTO", "BAIXO", "MEDIO"], [0.01, 0.98, 0.01])
        self.assertEqual(score, 1.5)

    def test_alto_com_alta_probabilidade_tem_score_alto(self):
        score = calcular_score_risco(["ALTO", "BAIXO", "MEDIO"], [0.80, 0.05, 0.15])
        self.assertEqual(score, 87.5)

    def test_override_critico_forca_score_maximo(self):
        score = calcular_score_risco(["ALTO", "BAIXO", "MEDIO"], [0.01, 0.98, 0.01], override_alto=True)
        self.assertEqual(score, 100.0)

    def test_score_nao_e_a_maior_probabilidade(self):
        # Regressao do bug da Sprint 3: o script Oracle usava max(probas) * 100
        probas = [0.10, 0.30, 0.60]  # ALTO, BAIXO, MEDIO
        self.assertNotEqual(calcular_score_risco(["ALTO", "BAIXO", "MEDIO"], probas), max(probas) * 100)

    def test_classe_desconhecida_e_rejeitada(self):
        with self.assertRaises(ValueError):
            calcular_score_risco(["CRITICO"], [1.0])

    def test_entrada_vazia_e_rejeitada(self):
        with self.assertRaises(ValueError):
            calcular_score_risco([], [])


class RegrasDominioTests(unittest.TestCase):
    BASE = {"umidade_solo": 20, "declividade": 5, "chuva_24h": 2, "temperatura": 25,
            "velocidade": 6, "idade_maquina": 3, "horas_operacao": 3}

    def test_verificar_max_lista_variaveis_criticas(self):
        em_max, variaveis = verificar_max({**self.BASE, "chuva_24h": 45, "velocidade": 21})
        self.assertTrue(em_max)
        self.assertEqual(variaveis, ["chuva_24h", "velocidade"])

    def test_recomendacao_de_atolamento(self):
        linha = {**self.BASE, "umidade_solo": 50}
        self.assertIn("atolamento", gerar_recomendacao(linha, "ALTO", ["umidade_solo"]))

    def test_baixo_segue_rota(self):
        self.assertEqual(gerar_recomendacao(self.BASE, "BAIXO", []), "Seguir rota atual")

    def test_categoria_mecanica(self):
        self.assertEqual(categorizar_alerta([], ["idade_maquina", "horas_operacao"]), "mecanico")

    def test_categoria_prioriza_variavel_no_maximo(self):
        self.assertEqual(categorizar_alerta(["declividade"], ["idade_maquina", "horas_operacao"]), "operacional")


if __name__ == "__main__":
    unittest.main()
