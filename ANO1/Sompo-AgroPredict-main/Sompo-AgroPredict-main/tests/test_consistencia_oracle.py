"""SQLite e Oracle devem gravar o mesmo score para a mesma entrada (feedback Sprint 3)."""

import random
import sys
import unittest

import pandas as pd

import apoio

sys.path.insert(0, str(apoio.RAIZ / "src" / "sql"))
import inserir_predicoes  # noqa: E402

from agropredict.entrada import FEATURES  # noqa: E402


class _Var:
    def __init__(self, valor):
        self.valor = valor

    def getvalue(self):
        return [self.valor]


class CursorFalso:
    """Captura os INSERTs que seriam enviados ao Oracle."""

    def __init__(self):
        self.predicoes, self.alertas, self._seq = [], [], 0

    def var(self, _tipo):
        self._seq += 1
        return _Var(self._seq)

    def execute(self, sql, params):
        (self.predicoes if "INSERT INTO predicoes" in sql else self.alertas).append(params)

    def close(self):
        pass


class ConexaoFalsa:
    def __init__(self):
        self.cursor_falso = CursorFalso()

    def cursor(self):
        return self.cursor_falso

    def commit(self):
        pass


class ConsistenciaOracleTests(unittest.TestCase):
    def test_mesmo_score_no_sqlite_e_no_oracle(self):
        df = pd.read_csv(apoio.RAIZ / "src" / "data" / "dataset_v2.csv").sample(n=40, random_state=7)
        conn = ConexaoFalsa()
        inserir_predicoes.processar_lote(conn, apoio.modelo(), df, numero_oracle="NUMBER", rng=random.Random(1))
        enviados = conn.cursor_falso.predicoes
        self.assertEqual(len(enviados), len(df))

        with apoio.BancoTemporario() as b:
            for params, (_, linha) in zip(enviados, df[FEATURES].iterrows()):
                r = b.servico.processar(linha.to_dict(), 1, "op.teste")
                gravado = b.repo.consultar(
                    "SELECT score_risco, classe_risco, prob_alto, versao_modelo FROM predicoes WHERE id_predicao = ?",
                    [r.id_predicao],
                ).iloc[0]
                self.assertAlmostEqual(params["score"], gravado["score_risco"], places=6)
                self.assertEqual(params["classe"], gravado["classe_risco"])
                self.assertAlmostEqual(params["pa"], gravado["prob_alto"], places=9)
                self.assertEqual(params["versao"], gravado["versao_modelo"])

    def test_alertas_oracle_seguem_o_mesmo_criterio(self):
        df = pd.DataFrame([apoio.LEITURA_SEGURA, apoio.LEITURA_CRITICA])
        conn = ConexaoFalsa()
        contagem = inserir_predicoes.processar_lote(conn, apoio.modelo(), df, numero_oracle="NUMBER")
        self.assertEqual(contagem["alertas"], 1)
        self.assertEqual(conn.cursor_falso.alertas[0]["nivel"], "ALTO")

    def test_linha_invalida_e_ignorada_no_lote(self):
        df = pd.DataFrame([apoio.LEITURA_SEGURA, {**apoio.LEITURA_SEGURA, "velocidade": -5}])
        contagem = inserir_predicoes.processar_lote(ConexaoFalsa(), apoio.modelo(), df, numero_oracle="NUMBER")
        self.assertEqual((contagem["inseridas"], contagem["rejeitadas"]), (1, 1))


if __name__ == "__main__":
    unittest.main()
