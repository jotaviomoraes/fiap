"""Catálogo dos serviços da FarmTech e a aba que os dispara na dashboard.

Cada serviço roda como um processo separado, com o mesmo comando usado no
terminal. Serviços que pedem dados pelo teclado abrem em uma janela própria.
"""

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src"

CAPTURA = "captura"    # roda e mostra a saída na própria aba
TERMINAL = "terminal"  # abre uma janela de terminal
LINK = "link"          # abre uma página externa
AVISO = "aviso"        # só orienta o usuário

TEMPO_LIMITE = 180  # segundos
LIMITE_SAIDA = 12000  # caracteres exibidos na aba


@dataclass(frozen=True)
class Servico:
    chave: str
    fase: str
    nome: str
    descricao: str
    modo: str
    pasta: Path = RAIZ
    comando: tuple = ()
    variaveis: tuple = ()  # variáveis do .env sem as quais o serviço não funciona
    link: str = ""


@dataclass(frozen=True)
class Execucao:
    codigo: int | None
    saida: str
    expirou: bool = False


SERVICOS = (
    Servico(
        chave="gestao_manejo",
        fase="Fase 1 — Gestão da lavoura",
        nome="Gestão de manejo",
        descricao="Cadastra lavouras, calcula área e insumos e exporta o CSV.",
        modo=TERMINAL,
        pasta=SRC / "fase1_gestao_lavoura",
        comando=("python", "gestao_manejo.py"),
    ),
    Servico(
        chave="analise_r",
        fase="Fase 1 — Gestão da lavoura",
        nome="Estatística e meteorologia (R)",
        descricao="Calcula as estatísticas do CSV e consulta o clima.",
        modo=CAPTURA,
        pasta=SRC / "fase1_gestao_lavoura",
        comando=("Rscript", "analise_estatistica.R"),
    ),
    Servico(
        chave="previsao_chuva",
        fase="Fase 2 — Irrigação e colheita",
        nome="Previsão de chuva",
        descricao="Consulta a OpenWeather para Sorriso/MT e indica o valor para o ESP32.",
        modo=CAPTURA,
        pasta=SRC / "fase2_irrigacao_iot",
        comando=("python", "openweather_chuva.py"),
        variaveis=("OPENWEATHER_API_KEY",),
    ),
    Servico(
        chave="irrigacao_esp32",
        fase="Fase 2 — Irrigação e colheita",
        nome="Irrigação com ESP32",
        descricao="Abre a simulação do circuito no Wokwi.",
        modo=LINK,
        link="https://wokwi.com/projects/461759867509065729",
    ),
    Servico(
        chave="colheita_cana",
        fase="Fase 2 — Irrigação e colheita",
        nome="Colheita de cana",
        descricao="Registra colheitas e calcula as perdas. O Oracle usa as credenciais do .env.",
        modo=TERMINAL,
        pasta=SRC / "fase2_colheita_cana",
        comando=("python", "main.py"),
    ),
    Servico(
        chave="banco_oracle",
        fase="Fase 3 — Banco de dados",
        nome="Banco Oracle",
        descricao="Garante a tabela dos sensores e executa as 6 consultas da Fase 3.",
        modo=CAPTURA,
        pasta=SRC / "fase3_banco_oracle",
        comando=("python", "servico_oracle.py"),
        variaveis=("ORACLE_USER", "ORACLE_PASSWORD"),
    ),
    Servico(
        chave="recomendacao_culturas",
        fase="Fase 3 — Banco de dados",
        nome="Recomendação de culturas",
        descricao="Abre o notebook com os 5 classificadores no Jupyter.",
        modo=TERMINAL,
        pasta=SRC / "fase3_ml_recomendacao_culturas",
        comando=("python", "-m", "jupyter", "notebook", "recomendacao_culturas.ipynb"),
    ),
    Servico(
        chave="pipeline_ml",
        fase="Fase 4 — Dashboard e Data Science",
        nome="Pipeline de Machine Learning",
        descricao="Treina os regressores e mostra as métricas dos 3 alvos.",
        modo=CAPTURA,
        pasta=SRC / "dashboard",
        comando=("python", "farmtech_ml.py"),
    ),
    Servico(
        chave="rendimento_safras",
        fase="Fase 5 — Nuvem e ML",
        nome="Previsão de rendimento de safras",
        descricao="Abre o notebook de análise e previsão no Jupyter.",
        modo=TERMINAL,
        pasta=SRC / "fase5_ml_rendimento_safras",
        comando=("python", "-m", "jupyter", "notebook", "previsao_rendimento_safras.ipynb"),
    ),
    Servico(
        chave="deteccao_pragas",
        fase="Fase 6 — Visão computacional",
        nome="Detecção de pragas",
        descricao="Use a aba **Detecção de Pragas** para enviar uma foto.",
        modo=AVISO,
    ),
    Servico(
        chave="alertas_aws",
        fase="Fase 7 — Alertas na AWS",
        nome="Simulação de alertas dos sensores",
        descricao="Avalia as leituras dos sensores e mostra os alertas, sem enviar pelo SNS.",
        modo=CAPTURA,
        comando=("python", "-m", "src.aws.alertas_sensores"),
    ),
    Servico(
        chave="enviar_alertas_sensores",
        fase="Fase 7 — Alertas na AWS",
        nome="Enviar alertas dos sensores",
        descricao=(
            "Publica no Amazon SNS os alertas das leituras dos sensores. "
            "Cada clique envia e-mails aos funcionários."
        ),
        modo=CAPTURA,
        comando=("python", "-m", "src.aws.alertas_sensores", "--enviar"),
        variaveis=("FARMTECH_SNS_TOPIC_ARN",),
    ),
    Servico(
        chave="alertas_pragas",
        fase="Fase 7 — Alertas na AWS",
        nome="Simulação de alertas de pragas",
        descricao="Avalia a última detecção de pragas, sem enviar pelo SNS.",
        modo=CAPTURA,
        comando=("python", "-m", "src.aws.alertas_pragas"),
    ),
    Servico(
        chave="enviar_alertas_pragas",
        fase="Fase 7 — Alertas na AWS",
        nome="Enviar alertas de pragas",
        descricao=(
            "Publica no Amazon SNS os alertas da última detecção. "
            "Cada clique envia e-mails aos funcionários."
        ),
        modo=CAPTURA,
        comando=("python", "-m", "src.aws.alertas_pragas", "--enviar"),
        variaveis=("FARMTECH_SNS_TOPIC_ARN",),
    ),
)


def localizar_rscript():
    """Procura o Rscript no PATH e na pasta padrão de instalação do Windows."""
    caminho = shutil.which("Rscript")
    if caminho:
        return caminho
    programas = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    instalacoes = sorted(programas.glob("R/R-*/bin/Rscript.exe"))
    return str(instalacoes[-1]) if instalacoes else None


def resolver_comando(servico):
    """Troca o nome do programa pelo executável desta máquina."""
    programa, *argumentos = servico.comando
    if programa == "python":
        return [sys.executable, *argumentos]
    if programa == "Rscript":
        rscript = localizar_rscript()
        return [rscript, *argumentos] if rscript else None
    return list(servico.comando)


def listar_pendencias(servico):
    """Lista o que falta na máquina para o serviço funcionar."""
    pendencias = []
    if servico.comando and resolver_comando(servico) is None:
        pendencias.append("R não encontrado. Instale o R 4.x.")
    valores = dotenv_values(RAIZ / ".env")
    for variavel in servico.variaveis:
        if not (valores.get(variavel) or os.environ.get(variavel)):
            pendencias.append(f"Preencha {variavel} no arquivo .env.")
    return pendencias


def executar(servico, tempo_limite=TEMPO_LIMITE):
    """Roda o serviço e devolve o código de saída e o texto produzido."""
    ambiente = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    try:
        processo = subprocess.run(
            resolver_comando(servico),
            cwd=servico.pasta,
            env=ambiente,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=tempo_limite,
        )
    except subprocess.TimeoutExpired:
        return Execucao(None, "", expirou=True)
    return Execucao(processo.returncode, processo.stdout + processo.stderr)


def abrir_terminal(servico):
    """Abre o serviço em uma janela própria. Só funciona no Windows."""
    if os.name != "nt":
        return False
    subprocess.Popen(
        resolver_comando(servico),
        cwd=servico.pasta,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    return True


def texto_do_comando(servico):
    """Monta o comando para rodar à mão, a partir da raiz do projeto."""
    comando = " ".join(servico.comando)
    if servico.pasta == RAIZ:
        return comando
    return f"cd {servico.pasta.relative_to(RAIZ).as_posix()} && {comando}"


def _mostrar_execucao(servico, execucao):
    if execucao.expirou:
        st.error(f"O serviço passou de {TEMPO_LIMITE} segundos e foi encerrado.")
        return
    if execucao.codigo == 0:
        st.success("Concluído.")
    else:
        st.error(f"O serviço falhou (código {execucao.codigo}).")
    if execucao.saida.strip():
        st.code(execucao.saida[-LIMITE_SAIDA:], language=None)


def _mostrar_servico(servico):
    st.markdown(f"**{servico.nome}**  \n{servico.descricao}")

    if servico.modo == AVISO:
        return
    if servico.modo == LINK:
        st.link_button("Abrir", servico.link)
        return

    pendencias = listar_pendencias(servico)
    for pendencia in pendencias:
        st.warning(pendencia)

    rotulo = "▶️ Executar" if servico.modo == CAPTURA else "🖥️ Abrir no terminal"
    if st.button(rotulo, key=f"servico_{servico.chave}", disabled=bool(pendencias)):
        if servico.modo == CAPTURA:
            with st.spinner(f"Executando {servico.nome}..."):
                st.session_state[f"execucao_{servico.chave}"] = executar(servico)
        elif abrir_terminal(servico):
            st.info("Janela aberta. Continue por lá.")
        else:
            st.info("Rode o comando abaixo em um terminal.")

    execucao = st.session_state.get(f"execucao_{servico.chave}")
    if execucao:
        _mostrar_execucao(servico, execucao)

    st.caption(f"Terminal: `{texto_do_comando(servico)}`")


def renderizar_aba():
    """Desenha a aba com todos os serviços, agrupados por fase."""
    st.subheader("🧩 Serviços do Sistema")
    st.caption(
        "Dispare aqui os serviços de cada fase ou use o comando indicado no terminal."
    )
    fase_atual = None
    for servico in SERVICOS:
        if servico.fase != fase_atual:
            st.markdown(f"#### {servico.fase}")
            fase_atual = servico.fase
        with st.container(border=True):
            _mostrar_servico(servico)
