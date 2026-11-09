"""A replica Oracle so deve ser consultada quando o usuario solicitar."""

import tempfile
import unittest
from pathlib import Path

import apoio
from streamlit.testing.v1 import AppTest


class OperacaoUITests(unittest.TestCase):
    def test_replica_oracle_nao_e_consultada_automaticamente(self):
        from agropredict.config import encerrar_logging
        from paginas import operacao

        with tempfile.TemporaryDirectory() as pasta:
            codigo = f'''
import sys
sys.path[:0] = [{str(apoio.RAIZ / "src")!r}, {str(apoio.RAIZ / "src/dashboard")!r}]
import streamlit as st
from agropredict.fabrica import criar_contexto
from agropredict.seguranca import Sessao
from paginas import operacao
@st.cache_resource
def contexto_teste():
    return criar_contexto(db_path={str(Path(pasta) / "teste.db")!r}, backend="sqlite", com_oracle=False)
def historico_teste():
    st.session_state["consultas_oracle_teste"] += 1
    return None
st.session_state.setdefault("consultas_oracle_teste", 0)
st.session_state["sessao"] = Sessao("admin", "admin")
operacao.contexto = contexto_teste
operacao.capturar_posicao = lambda ciclo: None
operacao._historico_oracle = historico_teste
operacao.render()
'''
            originais = {nome: getattr(operacao, nome) for nome in ("contexto", "capturar_posicao", "_historico_oracle")}
            try:
                app = AppTest.from_string(codigo).run(timeout=30)
                self.assertFalse(app.exception)
                self.assertEqual(app.session_state["consultas_oracle_teste"], 0)
                app.button(key="consultar_replica_oracle").click().run(timeout=30)
                self.assertFalse(app.exception)
                self.assertEqual(app.session_state["consultas_oracle_teste"], 1)
                app.run(timeout=30)
                self.assertEqual(app.session_state["consultas_oracle_teste"], 1)
            finally:
                for nome, valor in originais.items():
                    setattr(operacao, nome, valor)
                encerrar_logging()
