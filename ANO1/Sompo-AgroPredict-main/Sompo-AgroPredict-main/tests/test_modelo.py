"""Modelo final: metadados, explicacao local, modelo legado e migracao de banco antigo."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import apoio

from agropredict.entrada import Leitura
from agropredict.modelo import ModeloIndisponivel, ModeloRisco
from agropredict.persistencia import MIGRACOES, SCHEMA, RepositorioSQLite
from agropredict.servico import ServicoAvaliacao

META = apoio.RAIZ / "src" / "modelo" / "modelo_meta.json"


class ModeloFinalTests(unittest.TestCase):
    def test_versao_e_metadados_vem_do_treino(self):
        meta = json.loads(META.read_text(encoding="utf-8"))
        modelo = apoio.modelo()
        self.assertEqual(modelo.versao, meta["versao"])
        self.assertEqual(set(modelo.classes), {"BAIXO", "MEDIO", "ALTO"})
        self.assertGreaterEqual(meta["metricas_teste"]["recall"]["ALTO"], 0.95)
        self.assertEqual(meta["metricas_teste"]["alto_previsto_como_baixo"], 0)

    def test_probabilidades_somam_um_e_classe_e_a_mais_provavel(self):
        classe, probs, _ = apoio.modelo().prever(Leitura.de_dict(apoio.LEITURA_CRITICA))
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=6)
        self.assertEqual(classe, max(probs, key=probs.get))

    def test_explicacao_aponta_as_variaveis_de_risco(self):
        leitura = Leitura.de_dict({**apoio.LEITURA_SEGURA, "velocidade": 17, "declividade": 23, "temperatura": 41})
        _, _, contribuicoes = apoio.modelo().prever(leitura)
        self.assertLessEqual(len(contribuicoes), 3)
        self.assertTrue(contribuicoes)
        self.assertTrue({c.variavel for c in contribuicoes} <= {"velocidade", "declividade", "temperatura"})
        self.assertEqual([c.impacto for c in contribuicoes], sorted((c.impacto for c in contribuicoes), reverse=True))

    def test_leitura_segura_nao_tem_contribuicoes_relevantes(self):
        _, _, contribuicoes = apoio.modelo().prever(Leitura.de_dict(apoio.LEITURA_SEGURA))
        self.assertEqual(contribuicoes, [])

    def test_modelo_legado_sem_metadados_continua_funcionando(self):
        legado = ModeloRisco.carregar(apoio.RAIZ / "src" / "modelo" / "modelo_v1.pkl")
        self.assertEqual(legado.versao, "v1.0")
        classe, probs, _ = legado.prever(Leitura.de_dict(apoio.LEITURA_CRITICA))
        self.assertIn(classe, probs)
        self.assertFalse(legado.importancias().empty)

    def test_arquivo_corrompido(self):
        with tempfile.TemporaryDirectory() as pasta:
            falso = Path(pasta) / "modelo.pkl"
            falso.write_bytes(b"nao e um pickle")
            with self.assertRaises(ModeloIndisponivel):
                ModeloRisco.carregar(falso)
            with self.assertRaises(ModeloIndisponivel):
                ModeloRisco.carregar(Path(pasta) / "inexistente.pkl")


class MigracaoTests(unittest.TestCase):
    def test_banco_da_sprint_3_e_atualizado_sem_perder_dados(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "antigo.db"
            conn = sqlite3.connect(caminho)
            conn.executescript(SCHEMA)
            conn.execute("INSERT INTO equipamentos VALUES (1,'COL-01','Colheitadeira','CR9.90','NH',2018,'F','R',1)")
            conn.execute(
                """INSERT INTO leituras (data_hora, id_equipamento, usuario, origem, umidade_solo, declividade,
                       chuva_24h, temperatura, velocidade, idade_maquina, horas_operacao, status_operacao)
                   VALUES ('2026-08-20 10:00:00', 1, 'op.antigo', 'dashboard', 18, 5, 2, 25, 6, 3, 3, 'Colheita')""")
            conn.execute("CREATE VIEW vw_predicoes AS SELECT * FROM predicoes")
            conn.commit()
            conn.close()

            repo = RepositorioSQLite(caminho)
            with repo.conexao() as c:
                self.assertEqual(c.execute("PRAGMA user_version").fetchone()[0], len(MIGRACOES))
                colunas = {r[1] for r in c.execute("PRAGMA table_info(leituras)")}
            self.assertIn("hash_entrada", colunas)
            self.assertEqual(repo.obter_leitura(1)["usuario"], "op.antigo")

            # Leitura antiga, sem hash, ainda pode ser processada
            resultado = ServicoAvaliacao(repo, apoio.modelo()).processar_leitura(1)
            self.assertEqual(resultado.avaliacao.classe_risco, "BAIXO")
            self.assertFalse(repo.consultar("SELECT * FROM vw_predicoes").empty)

            RepositorioSQLite(caminho)  # reabrir nao reaplica migracoes


if __name__ == "__main__":
    unittest.main()
