"""
app.py - Dashboard Sompo AgroPredict
-------------------------------------
Camada de interface. Autentica o usuario, descobre o perfil e monta a
navegacao apenas com as paginas que esse perfil pode ver. Toda regra de
negocio, persistencia e calculo de risco vive em `src/agropredict`.

Modo de execucao (a partir da raiz do repositorio):
    streamlit run src/dashboard/app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agropredict.modelo import ModeloIndisponivel  # noqa: E402
from agropredict.seguranca import PERFIS, SenhaFraca  # noqa: E402
from ui_comum import contexto  # noqa: E402
from scripts.simular_frota import popular_demonstracao  # noqa: E402

from paginas import alertas, auditoria, frota, manutencao, operacao  # noqa: E402

st.set_page_config(
    page_title="Sompo AgroPredict",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGINAS = [
    # (recurso, funcao, titulo, icone, url)
    ("operacao", operacao.render, "Operação em tempo real", "📡", "operacao"),
    ("frota", frota.render, "Frota e tendências", "🚜", "frota"),
    ("alertas", alertas.render, "Alertas", "🚨", "alertas"),
    ("manutencao", manutencao.render, "Manutenção", "🔧", "manutencao"),
    ("auditoria", auditoria.render, "Auditoria Sompo", "🔎", "auditoria"),
]


@st.cache_resource
def _usuario_bootstrap() -> str | None:
    """Garante o usuario definido por APP_USERNAME/APP_PASSWORD (perfil APP_PERFIL, padrao admin)."""
    usuario, senha = os.getenv("APP_USERNAME"), os.getenv("APP_PASSWORD")
    if not usuario or not senha:
        return None
    contexto().auth.cadastrar(usuario, senha, os.getenv("APP_PERFIL", "admin"))
    return usuario


@st.cache_resource(show_spinner="Preparando a frota fictícia para demonstração…")
def _dados_bootstrap() -> None:
    popular_demonstracao(contexto())


def carregar_contexto():
    try:
        ctx = contexto()
        _usuario_bootstrap()
        if os.getenv("APP_DEMO", "true").lower() in {"true", "1", "sim"}:
            _dados_bootstrap()
        return ctx
    except ModeloIndisponivel as exc:
        st.error(f"❌ {exc}")
    except SenhaFraca as exc:
        st.error(f"❌ APP_PASSWORD inválida: {exc}")
    except ValueError as exc:
        st.error(f"❌ Configuração inválida: {exc}")
    except RuntimeError as exc:
        st.error(f"❌ Não foi possível preparar a demonstração: {exc}")
    st.stop()


def tela_login(ctx) -> None:
    st.title("🔐 Acesso ao Sompo AgroPredict")

    if ctx.repo.listar_usuarios().empty:
        st.warning("Nenhum usuário cadastrado. Crie um usuário antes de entrar:")
        st.code(
            "python scripts/gerenciar_usuarios.py criar --usuario gestor1 --perfil gestor",
            language="bash",
        )
        st.caption(f"Perfis disponíveis: {', '.join(PERFIS)}")
        st.stop()

    with st.form("form_login"):
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        enviar = st.form_submit_button("Entrar", type="primary")

    if enviar:
        if ctx.auth.bloqueado(usuario.strip()):
            ctx.auth.autenticar(usuario, senha)  # registra a tentativa bloqueada
            st.error("Usuário temporariamente bloqueado por excesso de tentativas. Aguarde 15 minutos.")
            st.stop()
        sessao = ctx.auth.autenticar(usuario, senha)
        if sessao:
            st.session_state["sessao"] = sessao
            st.rerun()
        st.error("Usuário ou senha inválidos.")
    st.stop()


def main() -> None:
    ctx = carregar_contexto()
    sessao = st.session_state.get("sessao")
    if sessao is None:
        tela_login(ctx)
        return

    with st.sidebar:
        if os.getenv("APP_DEMO", "true").lower() in {"true", "1", "sim"}:
            st.caption("🧪 Demonstração com dados fictícios. Não usar para decisões reais.")
        st.markdown(f"**👤 {sessao.nome or sessao.usuario}**  \n{PERFIS[sessao.perfil]}")
        if st.button("Sair", key="logout"):
            ctx.auth.registrar_logout(sessao)
            st.session_state.clear()
            st.rerun()
        st.markdown("---")

    paginas = [
        st.Page(funcao, title=titulo, icon=icone, url_path=url)
        for recurso, funcao, titulo, icone, url in PAGINAS
        if sessao.pode(recurso)
    ]
    st.navigation(paginas).run()


main()
