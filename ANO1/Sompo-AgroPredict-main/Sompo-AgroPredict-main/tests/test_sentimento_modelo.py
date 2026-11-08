"""Consistência entre tokenização, classificação e curva de leitura bilíngue."""
import importlib.util
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/dashboard"))


@unittest.skipUnless(importlib.util.find_spec("torch"), "Requer PyTorch")
class SentimentoModeloTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from agropredict.feedback_modelo import AnalisadorFeedback
        cls.modelos = {idioma: AnalisadorFeedback(RAIZ / "src/modelo" / nome, idioma)
                       for idioma, nome in [("pt", "feedback_bilstm.pt"), ("en", "feedback_bilstm_en.pt")]}

    def test_ultimo_ponto_corresponde_a_predicao_do_texto(self):
        import torch
        from agropredict.feedback_modelo import codificar, tokenizar
        for idioma, texto in [("pt", "Gostei muito desta aplicação, excelente!"),
                              ("en", "I don't like this application, it is terrible.")]:
            with self.subTest(idioma=idioma):
                modelo = self.modelos[idioma]
                r = modelo.classificar(texto)
                self.assertEqual(r["palavras"], tokenizar(texto, idioma))
                self.assertEqual(len(r["palavras"]), len(r["leitura"]))
                self.assertEqual(r["leitura"][-1], r["prob_bom"])
                self.assertAlmostEqual(r["prob_bom"] + r["prob_ruim"], 1.)
                self.assertTrue(all(0 <= p <= 1 for p in r["leitura"]))
                with torch.inference_mode():
                    x = codificar([texto], modelo.indice, modelo.config["max_len"], idioma).to(modelo.device)
                    direto = torch.sigmoid(modelo.model(x)).item()
                self.assertAlmostEqual(direto, r["prob_bom"], places=5)

    def test_texto_curto_vazio_e_truncamento(self):
        for idioma, modelo in self.modelos.items():
            with self.subTest(idioma=idioma):
                for vazio in ["", "  ", "!!!"]:
                    with self.assertRaises(ValueError):
                        modelo.classificar(vazio)
                self.assertEqual(len(modelo.classificar("excellent")["leitura"]), 1)
                r = modelo.classificar("excellent " * 250)
                self.assertEqual(len(r["leitura"]), modelo.config["max_len"] - 1)

    def test_artefato_nao_pode_ser_usado_no_idioma_errado(self):
        from agropredict.feedback_modelo import AnalisadorFeedback
        with self.assertRaises(ValueError):
            AnalisadorFeedback(RAIZ / "src/modelo/feedback_bilstm.pt", "en")

    def test_grafico_preserva_valores_e_limiar(self):
        import numpy as np
        from paginas.feedback import grafico_leitura
        r = self.modelos["pt"].classificar("Gostei muito deste projeto.")
        fig = grafico_leitura(r)
        ax = fig.axes[0]
        np.testing.assert_allclose(ax.lines[0].get_ydata(), [.5, .5])
        np.testing.assert_allclose(ax.lines[1].get_ydata(), r["leitura"])
        self.assertEqual([x.get_text() for x in ax.get_xticklabels()], r["palavras"])
        self.assertEqual(ax.get_ylim(), (0., 1.))

    def test_raio_x_corresponde_a_remover_cada_palavra(self):
        import torch
        from agropredict.feedback_modelo import codificar
        for idioma, texto in [("pt", "Produto excelente zzqvxx"), ("en", "Excellent application zzqvxx")]:
            modelo = self.modelos[idioma]
            r = modelo.classificar(texto)
            self.assertEqual(len(r["importancia"]), len(r["palavras"]))
            self.assertEqual(len(r["unk"]), len(r["palavras"]))
            self.assertFalse(r["unk"][0])
            self.assertTrue(r["unk"][-1])
            for i in range(len(r["palavras"])):
                restante = " ".join(r["palavras"][:i] + r["palavras"][i+1:])
                with torch.inference_mode():
                    x = codificar([restante], modelo.indice, modelo.config["max_len"], idioma).to(modelo.device)
                    sem_palavra = torch.sigmoid(modelo.model(x)).item()
                self.assertAlmostEqual(r["importancia"][i], r["prob_bom"] - sem_palavra, places=5)
            self.assertEqual(r["acuracia_teste"], modelo.metricas["acuracia"])
            self.assertEqual(r["versao_modelo"], modelo.versao)

    def test_raio_x_escapa_html_e_indica_desconhecidas(self):
        from paginas.feedback import html_raio_x, diagnostico_tecnico
        r = self.modelos["en"].classificar("Excellent application zzqvxx")
        r["palavras"][0] = '<img src=x onerror="alert(1)">'
        markup = html_raio_x(r)
        self.assertNotIn("<img", markup)
        self.assertIn("&lt;img", markup)
        self.assertIn("underline dotted", markup)
        diag = diagnostico_tecnico(r)
        self.assertIn("BiLSTM IMDB", diag)
        self.assertIn("<UNK>", diag)
        self.assertIn(r["dispositivo"], diag)


if __name__ == "__main__":
    unittest.main()
