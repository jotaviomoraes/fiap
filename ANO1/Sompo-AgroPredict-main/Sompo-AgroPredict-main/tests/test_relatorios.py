"""Relatorios por equipamento, regiao, tipo de operacao, alertas e auditoria."""

import unittest
from datetime import date, datetime

import apoio

from agropredict.relatorios import Filtros, Relatorios


def _popular(b):
    """Equipamento 1 (Sorriso) seguro; equipamento 5 (Cascavel) critico."""
    ids = {}
    for i, hora in enumerate(("08:00:00", "10:00:00", "15:00:00")):
        ids[f"seguro{i}"] = b.servico.processar(
            apoio.LEITURA_SEGURA, 1, "op.carlos", data_hora=f"2026-09-20 {hora}")
        ids[f"critico{i}"] = b.servico.processar(
            {**apoio.LEITURA_CRITICA, "status_operacao": "Deslocamento"}, 5, "op.pedro",
            data_hora=f"2026-09-20 {hora}")
    return ids


class RelatoriosTests(unittest.TestCase):
    def test_resumo_e_ranking(self):
        with apoio.BancoTemporario() as b:
            _popular(b)
            r = Relatorios(b.repo)
            resumo = r.resumo(Filtros())
            self.assertEqual((resumo["total"], resumo["alto"]), (6, 3))

            ranking = r.ranking_equipamentos(Filtros())
            self.assertEqual(ranking["equipamento"].tolist(), ["TRA-02", "COL-01"])
            self.assertEqual(ranking.iloc[0]["qtd_alto"], 3)

    def test_filtros_de_regiao_periodo_e_operacao(self):
        with apoio.BancoTemporario() as b:
            _popular(b)
            r = Relatorios(b.repo)
            self.assertEqual(r.resumo(Filtros(regioes=["Sorriso - MT"]))["total"], 3)
            self.assertEqual(r.resumo(Filtros(status_operacao=["Deslocamento"]))["total"], 3)
            self.assertEqual(r.resumo(Filtros(data_inicio=date(2026, 9, 21)))["total"], 0)
            self.assertEqual(r.resumo(Filtros(data_inicio=date(2026, 9, 20), data_fim=date(2026, 9, 20)))["total"], 6)

    def test_tendencia_por_regiao_e_por_tipo_de_operacao(self):
        with apoio.BancoTemporario() as b:
            _popular(b)
            r = Relatorios(b.repo)
            por_regiao = r.tendencia_diaria(Filtros(), "regiao")
            self.assertEqual(sorted(por_regiao.columns), ["Cascavel - PR", "Sorriso - MT"])
            por_tipo = r.resumo_por_dimensao(Filtros(), "status_operacao")
            self.assertEqual(set(por_tipo["grupo"]), {"Colheita", "Deslocamento"})
            with self.assertRaises(KeyError):
                r.tendencia_diaria(Filtros(), "coluna; DROP TABLE leituras")

    def test_alertas_do_operador_e_aderencia(self):
        with apoio.BancoTemporario() as b:
            ids = _popular(b)
            b.servico.responder_alerta(ids["critico0"].id_alerta, "RESPEITOU", "op.pedro")
            b.servico.responder_alerta(ids["critico1"].id_alerta, "IGNOROU", "op.pedro")
            r = Relatorios(b.repo)

            self.assertTrue(r.listar_alertas(Filtros(usuario="op.carlos")).empty)
            self.assertEqual(len(r.listar_alertas(Filtros(usuario="op.pedro"))), 3)
            self.assertEqual(len(r.listar_alertas(Filtros(), acoes=["PENDENTE"])), 1)

            aderencia = r.aderencia_operadores(Filtros()).set_index("operador")
            self.assertEqual(aderencia.loc["op.pedro", "aderencia_pct"], 50.0)
            self.assertEqual(aderencia.loc["op.pedro", "pendentes"], 1)

    def test_forense_e_auditoria(self):
        with apoio.BancoTemporario() as b:
            ids = _popular(b)
            r = Relatorios(b.repo)
            janela = r.forense(5, datetime(2026, 9, 20, 11, 0), janela_horas=4)
            self.assertEqual(len(janela), 2)

            auditoria = r.auditoria_predicao(ids["critico2"].id_predicao)
            for campo in ("prob_baixo", "prob_medio", "prob_alto", "versao_modelo", "hash_modelo",
                          "motivo_override", "fonte_clima", "regiao"):
                self.assertIn(campo, auditoria)
            self.assertEqual(auditoria["alerta"]["nivel"], "ALTO")
            self.assertIsNone(r.auditoria_predicao(99999))

    def test_comportamento_preventivo_do_produtor(self):
        with apoio.BancoTemporario() as b:
            # Fazenda Aurora (equip. 1): 30 operacoes seguras -> Excelente
            for i in range(30):
                b.servico.processar(apoio.LEITURA_SEGURA, 1, "op.carlos", data_hora=f"2026-09-20 08:{i:02d}:00")
            # Fazenda Santa Clara (equip. 5): 30 criticas, alertas ignorados -> Critico
            for i in range(30):
                r = b.servico.processar(apoio.LEITURA_CRITICA, 5, "op.pedro", data_hora=f"2026-09-20 09:{i:02d}:00")
                b.servico.responder_alerta(r.id_alerta, "IGNOROU", "op.pedro")
            # Fazenda Boa Vista (equip. 3): poucas operacoes -> dados insuficientes
            b.servico.processar(apoio.LEITURA_SEGURA, 3, "op.joao", data_hora="2026-09-20 10:00:00")

            df = Relatorios(b.repo).comportamento_produtor(Filtros()).set_index("fazenda")
            self.assertEqual(df.loc["Fazenda Aurora", "faixa"], "Excelente")
            self.assertEqual(df.loc["Fazenda Aurora", "score_comportamento"], 90.0)  # 50 + 30 + 20*0.5
            self.assertEqual(df.loc["Fazenda Santa Clara", "faixa"], "Crítico")
            self.assertEqual(df.loc["Fazenda Santa Clara", "aderencia_pct"], 0.0)
            self.assertEqual(df.loc["Fazenda Boa Vista", "faixa"], "Dados insuficientes")

    def test_indicadores_de_qualidade_da_coleta(self):
        with apoio.BancoTemporario() as b:
            b.servico.processar(apoio.LEITURA_SEGURA, 1, "op.carlos", data_hora="2026-09-20 08:00:00",
                                fontes={"clima": "open-meteo", "velocidade": "manual"})
            with self.assertRaises(ValueError):
                b.servico.processar({**apoio.LEITURA_SEGURA, "velocidade": None}, 1, "op.carlos")
            q = Relatorios(b.repo).qualidade_dados(Filtros())
            self.assertEqual(q["status"].set_index("status")["leituras"].to_dict(), {"PROCESSADA": 1})
            self.assertEqual(q["integridade"], {"total": 1, "com_hash": 1, "processadas_sem_predicao": 0})
            self.assertEqual(q["rejeicoes_por_tipo"], {"INVALIDA": 1})
            fontes = q["fontes"].set_index("fonte")
            self.assertEqual(fontes.loc["velocidade", "pct_manual"], 100.0)
            self.assertEqual(fontes.loc["clima", "pct_manual"], 0.0)

    def test_prioridade_de_manutencao(self):
        with apoio.BancoTemporario() as b:
            # Idade e horas acima do limiar dominam as variaveis em alerta -> categoria mecanica (MEDIO)
            mecanica = {**apoio.LEITURA_SEGURA, "idade_maquina": 17, "horas_operacao": 12,
                        "velocidade": 14, "declividade": 15, "temperatura": 36}
            for hora in ("09", "10", "11"):
                b.servico.processar(mecanica, 5, "op.pedro", data_hora=f"2026-09-20 {hora}:00:00")
            b.servico.processar(apoio.LEITURA_SEGURA, 1, "op.carlos", data_hora="2026-09-20 09:00:00")
            df = Relatorios(b.repo).manutencao(Filtros()).set_index("equipamento")
            self.assertEqual(df.loc["COL-01", "prioridade"], "BAIXA")
            self.assertEqual(df.loc["TRA-02", "alertas_mecanicos"], 3)
            self.assertEqual(df.loc["TRA-02", "prioridade"], "ALTA")


if __name__ == "__main__":
    unittest.main()
