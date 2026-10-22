"""Fluxo de ponta a ponta: entrada -> banco -> modelo -> saida, sem interface."""

import json
import sqlite3
import unittest

import apoio

from agropredict.entrada import Leitura, LeituraInvalida
from agropredict.integridade import hash_leitura
from agropredict.regras import calcular_score_risco
from agropredict.servico import ErroProcessamento, LeituraDuplicada


class FluxoPontaAPontaTests(unittest.TestCase):
    def test_leitura_e_gravada_antes_do_modelo(self):
        with apoio.BancoTemporario() as b:
            id_leitura = b.servico.registrar_leitura(apoio.LEITURA_SEGURA, 1, "op.teste")
            leitura = b.repo.obter_leitura(id_leitura)
            self.assertEqual(leitura["status_processamento"], "PENDENTE")
            self.assertEqual(b.repo.consultar("SELECT COUNT(*) n FROM predicoes")["n"][0], 0)

            resultado = b.servico.processar_leitura(id_leitura)
            self.assertEqual(b.repo.obter_leitura(id_leitura)["status_processamento"], "PROCESSADA")
            self.assertEqual(resultado.id_leitura, id_leitura)

    def test_modelo_usa_os_valores_do_banco(self):
        # Corrige a leitura no banco (valor + hash coerentes): a predicao reflete o banco, nao a tela.
        with apoio.BancoTemporario() as b:
            id_leitura = b.servico.registrar_leitura(apoio.LEITURA_SEGURA, 1, "op.teste")
            linha = b.repo.obter_leitura(id_leitura)
            corrigida = Leitura.de_dict({**apoio.LEITURA_SEGURA, "chuva_24h": 45})
            novo_hash = hash_leitura(corrigida, 1, linha["data_hora"], linha["usuario"])
            with b.repo.conexao() as conn:
                conn.execute("UPDATE leituras SET chuva_24h = 45, hash_entrada = ? WHERE id_leitura = ?",
                             (novo_hash, id_leitura))
            resultado = b.servico.processar_leitura(id_leitura)
            self.assertEqual(resultado.leitura.chuva_24h, 45)
            self.assertTrue(resultado.avaliacao.override_aplicado)
            self.assertEqual(resultado.avaliacao.classe_risco, "ALTO")

    def test_alteracao_indevida_no_banco_e_detectada(self):
        with apoio.BancoTemporario() as b:
            id_leitura = b.servico.registrar_leitura(apoio.LEITURA_SEGURA, 1, "op.teste")
            with b.repo.conexao() as conn:
                conn.execute("UPDATE leituras SET velocidade = 19 WHERE id_leitura = ?", (id_leitura,))
            with self.assertRaises(ErroProcessamento):
                b.servico.processar_leitura(id_leitura)
            leitura = b.repo.obter_leitura(id_leitura)
            self.assertEqual(leitura["status_processamento"], "ERRO")
            self.assertIn("integridade", leitura["erro_processamento"])
            self.assertEqual(b.repo.consultar("SELECT COUNT(*) n FROM predicoes")["n"][0], 0)

    def test_retransmissao_identica_e_rejeitada_e_registrada(self):
        with apoio.BancoTemporario() as b:
            b.servico.processar(apoio.LEITURA_SEGURA, 1, "op.teste", data_hora="2026-09-20 10:00:00")
            with self.assertRaises(LeituraDuplicada):
                b.servico.processar(apoio.LEITURA_SEGURA, 1, "op.teste", data_hora="2026-09-20 10:00:00")
            # Mesmo valor em outro horario nao e duplicata
            b.servico.processar(apoio.LEITURA_SEGURA, 1, "op.teste", data_hora="2026-09-20 10:00:10")
            rejeicoes = b.repo.consultar("SELECT tipo, motivo FROM rejeicoes")
            self.assertEqual(rejeicoes["tipo"].tolist(), ["DUPLICADA"])
            self.assertEqual(b.repo.consultar("SELECT COUNT(*) n FROM leituras")["n"][0], 2)

    def test_entrada_invalida_fica_registrada_como_rejeicao(self):
        with apoio.BancoTemporario() as b:
            with self.assertRaises(LeituraInvalida):
                b.servico.processar({**apoio.LEITURA_SEGURA, "velocidade": 250}, 1, "op.teste", origem="teste")
            rejeicao = b.repo.consultar("SELECT * FROM rejeicoes").iloc[0]
            self.assertEqual((rejeicao["tipo"], rejeicao["origem"], rejeicao["usuario"]), ("INVALIDA", "teste", "op.teste"))
            self.assertIn("velocidade", rejeicao["motivo"])
            self.assertIn("250", rejeicao["dados"])

    def test_predicao_guarda_explicacao(self):
        with apoio.BancoTemporario() as b:
            r = b.servico.processar({**apoio.LEITURA_SEGURA, "velocidade": 17, "declividade": 23, "temperatura": 41},
                                    1, "op.teste")
            explicacao = json.loads(b.repo.consultar(
                "SELECT explicacao FROM predicoes WHERE id_predicao = ?", [r.id_predicao])["explicacao"][0])
            variaveis = [c["variavel"] for c in explicacao]
            self.assertTrue(variaveis)
            self.assertTrue(set(variaveis) <= {"velocidade", "declividade", "temperatura"})
            self.assertTrue(all(c["impacto"] > 0 for c in explicacao))

    def test_predicao_guarda_probabilidades_versao_e_override(self):
        with apoio.BancoTemporario() as b:
            r = b.servico.processar(apoio.LEITURA_CRITICA, 3, "op.teste")
            linha = b.repo.consultar("SELECT * FROM predicoes WHERE id_predicao = ?", [r.id_predicao]).iloc[0]
            self.assertAlmostEqual(linha["prob_baixo"] + linha["prob_medio"] + linha["prob_alto"], 1.0, places=6)
            self.assertEqual(linha["versao_modelo"], apoio.modelo().versao)
            self.assertEqual(linha["hash_modelo"], apoio.modelo().hash_arquivo)
            self.assertEqual(linha["override_aplicado"], 1)
            self.assertIn("chuva_24h", linha["motivo_override"])

    def test_score_gravado_e_o_risco_esperado(self):
        with apoio.BancoTemporario() as b:
            r = b.servico.processar(apoio.LEITURA_SEGURA, 1, "op.teste")
            linha = b.repo.consultar("SELECT * FROM predicoes WHERE id_predicao = ?", [r.id_predicao]).iloc[0]
            esperado = calcular_score_risco(
                ["BAIXO", "MEDIO", "ALTO"], [linha["prob_baixo"], linha["prob_medio"], linha["prob_alto"]]
            )
            self.assertAlmostEqual(linha["score_risco"], esperado, places=2)

    def test_risco_alto_gera_alerta_pendente(self):
        with apoio.BancoTemporario() as b:
            r = b.servico.processar(apoio.LEITURA_CRITICA, 3, "op.teste")
            self.assertIsNotNone(r.id_alerta)
            alerta = b.repo.consultar("SELECT * FROM alertas WHERE id_alerta = ?", [r.id_alerta]).iloc[0]
            self.assertEqual(alerta["nivel"], "ALTO")
            self.assertEqual(alerta["acao_tomada"], "PENDENTE")

            self.assertTrue(b.servico.responder_alerta(r.id_alerta, "RESPEITOU", "op.teste"))
            self.assertFalse(b.servico.responder_alerta(r.id_alerta, "IGNOROU", "op.teste"))

    def test_risco_baixo_nao_gera_alerta(self):
        with apoio.BancoTemporario() as b:
            r = b.servico.processar(apoio.LEITURA_SEGURA, 1, "op.teste")
            self.assertEqual(r.avaliacao.classe_risco, "BAIXO")
            self.assertIsNone(r.id_alerta)

    def test_entrada_invalida_nao_chega_ao_banco(self):
        with apoio.BancoTemporario() as b:
            with self.assertRaises(LeituraInvalida):
                b.servico.processar({**apoio.LEITURA_SEGURA, "velocidade": None}, 1, "op.teste")
            self.assertEqual(b.repo.consultar("SELECT COUNT(*) n FROM leituras")["n"][0], 0)

    def test_equipamento_inexistente_e_rejeitado(self):
        with apoio.BancoTemporario() as b:
            with self.assertRaises(ValueError):
                b.servico.processar(apoio.LEITURA_SEGURA, 999, "op.teste")

    def test_leitura_corrompida_no_banco_fica_marcada_com_erro(self):
        with apoio.BancoTemporario() as b:
            id_leitura = b.servico.registrar_leitura(apoio.LEITURA_SEGURA, 1, "op.teste")
            with b.repo.conexao() as conn:
                conn.execute("UPDATE leituras SET velocidade = 999 WHERE id_leitura = ?", (id_leitura,))
            with self.assertRaises(ErroProcessamento):
                b.servico.processar_leitura(id_leitura)
            leitura = b.repo.obter_leitura(id_leitura)
            self.assertEqual(leitura["status_processamento"], "ERRO")
            self.assertIn("velocidade", leitura["erro_processamento"])

    def test_leitura_nao_e_processada_duas_vezes(self):
        with apoio.BancoTemporario() as b:
            r = b.servico.processar(apoio.LEITURA_SEGURA, 1, "op.teste")
            with self.assertRaises(ErroProcessamento):
                b.servico.processar_leitura(r.id_leitura)

    def test_pendentes_sao_reprocessados(self):
        with apoio.BancoTemporario() as b:
            ids = [b.servico.registrar_leitura(apoio.LEITURA_SEGURA, 1, "op.teste",
                                               data_hora=f"2026-09-20 10:00:0{i}") for i in range(3)]
            resultados = b.servico.processar_pendentes()
            self.assertEqual([r.id_leitura for r in resultados], ids)

    def test_banco_rejeita_classe_fora_do_dominio(self):
        with apoio.BancoTemporario() as b:
            id_leitura = b.servico.registrar_leitura(apoio.LEITURA_SEGURA, 1, "op.teste")
            with self.assertRaises(sqlite3.IntegrityError):
                with b.repo.conexao() as conn:
                    conn.execute(
                        """INSERT INTO predicoes (id_leitura, data_hora, classe_modelo, classe_risco, score_risco,
                               prob_baixo, prob_medio, prob_alto, override_aplicado, recomendacao,
                               versao_modelo, hash_modelo)
                           VALUES (?, '2026-01-01', 'CRITICO', 'CRITICO', 50, 0, 0, 1, 0, 'x', 'v', 'h')""",
                        (id_leitura,),
                    )


if __name__ == "__main__":
    unittest.main()
