import math
import unittest

import apoio

from agropredict.entrada import Leitura, LeituraInvalida


class ValidacaoEntradaTests(unittest.TestCase):
    def test_leitura_valida(self):
        leitura = Leitura.de_dict(apoio.LEITURA_SEGURA)
        self.assertEqual(leitura.status_operacao, "Colheita")
        self.assertIsInstance(leitura.velocidade, float)

    def test_aceita_numeros_em_texto(self):
        leitura = Leitura.de_dict({**apoio.LEITURA_SEGURA, "velocidade": "7.5"})
        self.assertEqual(leitura.velocidade, 7.5)

    def test_campo_ausente(self):
        dados = dict(apoio.LEITURA_SEGURA)
        del dados["chuva_24h"]
        with self.assertRaises(LeituraInvalida) as ctx:
            Leitura.de_dict(dados)
        self.assertIn("chuva_24h ausente", ctx.exception.problemas)

    def test_valor_nao_numerico_e_nan(self):
        with self.assertRaises(LeituraInvalida) as ctx:
            Leitura.de_dict({**apoio.LEITURA_SEGURA, "temperatura": "quente", "declividade": math.nan})
        self.assertEqual(len(ctx.exception.problemas), 2)

    def test_fora_da_faixa_fisica(self):
        with self.assertRaises(LeituraInvalida):
            Leitura.de_dict({**apoio.LEITURA_SEGURA, "velocidade": 250})
        with self.assertRaises(LeituraInvalida):
            Leitura.de_dict({**apoio.LEITURA_SEGURA, "umidade_solo": -1})

    def test_status_invalido(self):
        with self.assertRaises(LeituraInvalida):
            Leitura.de_dict({**apoio.LEITURA_SEGURA, "status_operacao": "Plantio"})

    def test_reporta_todos_os_problemas_de_uma_vez(self):
        with self.assertRaises(LeituraInvalida) as ctx:
            Leitura.de_dict({})
        self.assertEqual(len(ctx.exception.problemas), 8)


if __name__ == "__main__":
    unittest.main()
