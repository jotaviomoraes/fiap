"""
validar_integracao.py
---------------------
Valida a integracao com as fontes de dados (reais e simuladas) e gera a
evidencia `document/evidencias/validacao_integracao.md`.

Verificacoes (todas em um banco SQLite temporario, sem tocar no banco real):
  A. Fonte real: consulta a Open-Meteo em 3 regioes da frota e envia o clima
     real pelo fluxo completo (entrada -> banco -> modelo -> saida)
  B. Falhas da fonte real: timeout, erro HTTP e resposta invalida viram
     `ok=False` e o sistema cai para entrada manual, sem excecao
  C. GPS simulado: trajeto com velocidade conhecida e um salto de sinal
  D. Lote de telemetria simulada com entradas invalidas e retransmissoes
     injetadas: nenhuma leitura perdida, nenhum dado corrompido
  E. Corrupcao no banco: leitura alterada depois de gravada e recusada
  F. Consistencia SQLite x Oracle: mesmo score nas duas persistencias

Uso (a partir da raiz do repositorio):
    python scripts/validar_integracao.py                 # 500 leituras
    python scripts/validar_integracao.py --leituras 2000
    python scripts/validar_integracao.py --sem-rede      # pula a consulta real

Codigo de saida 1 se alguma verificacao falhar.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "scripts"))

from agropredict import clima, oracle  # noqa: E402
from agropredict.config import encerrar_logging  # noqa: E402
from agropredict.entrada import FEATURES, FEATURES_NUMERICAS, Leitura, LeituraInvalida  # noqa: E402
from agropredict.fabrica import criar_contexto  # noqa: E402
from agropredict.integridade import hash_leitura  # noqa: E402
from agropredict.markdown import tabela_markdown  # noqa: E402
from agropredict.regras import calcular_score_risco  # noqa: E402
from agropredict.servico import ErroProcessamento, LeituraDuplicada  # noqa: E402
from agropredict.telemetria import calcular_velocidade_kmh  # noqa: E402
from simular_frota import gerar_leitura  # noqa: E402

SAIDA = RAIZ / "document" / "evidencias" / "validacao_integracao.md"
REGIOES = {  # coordenadas aproximadas das regioes da frota ficticia
    "Sorriso - MT": (-12.545, -55.711),
    "Rio Verde - GO": (-17.798, -50.928),
    "Cascavel - PR": (-24.955, -53.455),
}


class Verificacoes:
    def __init__(self):
        self.linhas: list[dict] = []

    def registrar(self, grupo: str, verificacao: str, esperado: str, obtido: str, ok: bool | None) -> None:
        situacao = "✅ OK" if ok else ("⚠️ AVISO" if ok is None else "❌ FALHOU")
        self.linhas.append({"Grupo": grupo, "Verificação": verificacao, "Esperado": esperado,
                            "Obtido": obtido, "Resultado": situacao})
        print(f"  {situacao:10} {grupo} · {verificacao}: {obtido}")

    @property
    def falhas(self) -> int:
        return sum(1 for linha in self.linhas if "FALHOU" in linha["Resultado"])


def a_fonte_real(ctx, v: Verificacoes, sem_rede: bool) -> pd.DataFrame:
    print("[A] Fonte real (Open-Meteo)")
    linhas = []
    if sem_rede:
        v.registrar("A. Fonte real", "Consulta à Open-Meteo", "resposta válida", "pulada (--sem-rede)", None)
        return pd.DataFrame()
    for regiao, (lat, lon) in REGIOES.items():
        inicio = time.perf_counter()
        dados = clima.buscar_clima_atual(lat, lon)
        latencia = (time.perf_counter() - inicio) * 1000
        if not dados["ok"]:
            v.registrar("A. Fonte real", f"Open-Meteo em {regiao}", "resposta válida",
                        f"indisponível: {dados.get('erro', '')[:60]}", None)
            continue
        faixas_ok = (-10 <= dados["temperatura"] <= 60 and dados["chuva_24h"] >= 0
                     and (dados["umidade_solo"] is None or 0 <= dados["umidade_solo"] <= 100))
        entrada = {"temperatura": dados["temperatura"], "chuva_24h": dados["chuva_24h"],
                   "umidade_solo": dados["umidade_solo"] if dados["umidade_solo"] is not None else 20.0,
                   "declividade": 8.0, "velocidade": 7.0, "idade_maquina": 5.0, "horas_operacao": 4.0,
                   "status_operacao": "Colheita"}
        r = ctx.servico.processar(entrada, 1, "validacao", origem="validacao-real",
                                  fontes={"clima": "open-meteo", "umidade": "open-meteo"})
        gravada = ctx.repo.obter_leitura(r.id_leitura)
        preservado = all(gravada[c] == entrada[c] for c in ("temperatura", "chuva_24h", "umidade_solo"))
        v.registrar("A. Fonte real", f"Open-Meteo em {regiao} → fluxo completo",
                    "campos em faixa física, gravados sem alteração e avaliados",
                    f"{latencia:.0f} ms · {dados['temperatura']}°C · {dados['chuva_24h']} mm · "
                    f"solo {dados['umidade_solo']}% → predição #{r.id_predicao} {r.avaliacao.classe_risco}",
                    faixas_ok and preservado)
        linhas.append({"região": regiao, "latência (ms)": round(latencia), "temperatura (°C)": dados["temperatura"],
                       "chuva 24h (mm)": dados["chuva_24h"], "umidade do solo (%)": dados["umidade_solo"],
                       "classe": r.avaliacao.classe_risco, "score": r.avaliacao.score_risco})
    return pd.DataFrame(linhas)


def b_falhas_da_fonte(v: Verificacoes) -> None:
    print("[B] Falhas simuladas da Open-Meteo")
    invalida = mock.Mock(raise_for_status=mock.Mock(), json=mock.Mock(side_effect=ValueError("JSON inválido")))
    http_500 = mock.Mock(raise_for_status=mock.Mock(side_effect=requests.HTTPError("HTTP 500")))
    incompleta = mock.Mock(raise_for_status=mock.Mock(), json=mock.Mock(return_value={"current": {}}))
    cenarios = {
        "timeout": mock.Mock(side_effect=requests.Timeout("tempo esgotado")),
        "sem conexão": mock.Mock(side_effect=requests.ConnectionError("sem rede")),
        "HTTP 500": mock.Mock(return_value=http_500),
        "JSON inválido": mock.Mock(return_value=invalida),
        "resposta incompleta": mock.Mock(return_value=incompleta),
    }
    for nome, get in cenarios.items():
        with mock.patch.object(clima.requests, "get", get):
            try:
                dados = clima.buscar_clima_atual(0, 0)
                ok = dados["ok"] is False and dados["temperatura"] is None
                obtido = f"ok=False, erro registrado ({dados.get('erro', '')[:40]})"
            except Exception as exc:  # qualquer excecao aqui e falha de robustez
                ok, obtido = False, f"exceção: {exc}"
        v.registrar("B. Falha da fonte", nome, "ok=False, sem exceção, fallback manual", obtido, ok)


def c_gps(v: Verificacoes) -> None:
    print("[C] GPS simulado")
    # Trajeto a 12 km/h para o norte, uma leitura a cada 10 s, com um salto de sinal no meio
    passo_lat = (12 / 3600 * 10) / 111.19
    pontos = [{"lat": -12.5 + i * passo_lat, "lon": -55.7, "timestamp": 1000.0 + i * 10} for i in range(30)]
    pontos[15] = {**pontos[15], "lat": pontos[15]["lat"] + 0.05}  # salto de ~5,5 km em 10 s
    velocidades = [calcular_velocidade_kmh(atual, anterior) for anterior, atual in zip(pontos, pontos[1:])]
    validas = [vel for vel, origem in velocidades if origem == "calculada"]
    descartadas = sum(1 for vel, _ in velocidades if vel is None)
    erro_max = max(abs(vel - 12) for vel in validas)
    v.registrar("C. GPS", "Velocidade calculada em trajeto a 12 km/h", "erro ≤ 0,5 km/h nas leituras válidas",
                f"{len(validas)} leituras, erro máximo {erro_max:.2f} km/h", erro_max <= 0.5)
    v.registrar("C. GPS", "Salto de sinal (≈2000 km/h)", "descartado, cai para manual",
                f"{descartadas} leitura(s) descartada(s)", descartadas >= 1)
    chip = calcular_velocidade_kmh({**pontos[0], "speed_ms": 3.5}, None)
    v.registrar("C. GPS", "Velocidade do chip GPS (3,5 m/s)", "12,6 km/h, origem gps_chip", str(chip),
                chip == (12.6, "gps_chip"))


def _injetar_invalida(dados: dict, rng) -> dict:
    campo = rng.choice(FEATURES_NUMERICAS)
    problema = rng.choice(["ausente", "texto", "fora da faixa", "status"])
    if problema == "ausente":
        return {**dados, campo: None}
    if problema == "texto":
        return {**dados, campo: "erro"}
    if problema == "status":
        return {**dados, "status_operacao": "Plantio"}
    return {**dados, campo: 999.0}


def d_lote_simulado(ctx, v: Verificacoes, n: int, seed: int = 11) -> dict:
    print(f"[D] Lote de {n} leituras simuladas com problemas injetados")
    rng = np.random.default_rng(seed)
    equipamentos = ctx.repo.listar_equipamentos().to_dict("records")
    inicio = datetime(2026, 9, 1, 6, 0, 0)
    enviados, aceitos = [], {}
    rej_invalidas = rej_duplicadas = erros = 0

    for i in range(n):
        equip = equipamentos[i % len(equipamentos)]
        momento = inicio + timedelta(minutes=7 * i)
        dados = gerar_leitura(rng, equip, momento, chuva_dia=float(rng.gamma(2.0, 6.0)))
        sorteio = rng.random()
        if sorteio < 0.05:
            dados = _injetar_invalida(dados, rng)
        data_hora = momento.isoformat(sep=" ", timespec="seconds")
        envios = [dados, dados] if 0.05 <= sorteio < 0.08 else [dados]  # retransmissao identica
        for payload in envios:
            enviados.append(payload)
            try:
                r = ctx.servico.processar(payload, equip["id_equipamento"], "validacao", origem="validacao-lote",
                                          data_hora=data_hora)
                aceitos[r.id_leitura] = payload
            except LeituraInvalida:
                rej_invalidas += 1
            except LeituraDuplicada:
                rej_duplicadas += 1
            except ErroProcessamento:
                erros += 1

    total = len(enviados)
    v.registrar("D. Lote simulado", "Conservação: enviadas = gravadas + rejeitadas",
                "nenhuma leitura perdida",
                f"{total} enviadas = {len(aceitos)} gravadas + {rej_invalidas} inválidas + {rej_duplicadas} duplicadas"
                f" + {erros} erros", total == len(aceitos) + rej_invalidas + rej_duplicadas + erros and erros == 0)

    rejeicoes = ctx.repo.consultar(
        "SELECT tipo, COUNT(*) n FROM rejeicoes WHERE origem = 'validacao-lote' GROUP BY tipo"
    ).set_index("tipo")["n"].to_dict()
    v.registrar("D. Lote simulado", "Toda rejeição fica registrada com motivo",
                f"{rej_invalidas} inválidas + {rej_duplicadas} duplicadas em `rejeicoes`",
                str(rejeicoes), rejeicoes.get("INVALIDA", 0) == rej_invalidas
                and rejeicoes.get("DUPLICADA", 0) == rej_duplicadas)

    gravadas = ctx.repo.consultar(
        "SELECT * FROM vw_predicoes WHERE origem = 'validacao-lote'").set_index("id_leitura")
    pendentes = ctx.repo.consultar(
        "SELECT COUNT(*) n FROM leituras WHERE origem = 'validacao-lote' AND status_processamento != 'PROCESSADA'"
    )["n"][0]
    v.registrar("D. Lote simulado", "Toda leitura gravada tem exatamente uma predição", "0 sem predição",
                f"{len(gravadas)} predições para {len(aceitos)} leituras; {pendentes} não processadas",
                len(gravadas) == len(aceitos) and pendentes == 0 and gravadas.index.is_unique)

    divergentes = 0
    for id_leitura, payload in aceitos.items():
        linha = gravadas.loc[id_leitura]
        if any(abs(float(linha[c]) - float(payload[c])) > 0 for c in FEATURES_NUMERICAS) \
                or linha["status_operacao"] != payload["status_operacao"]:
            divergentes += 1
    v.registrar("D. Lote simulado", "Valores gravados = valores enviados (ida e volta)", "0 divergências",
                f"{divergentes} divergências em {len(aceitos)} leituras × {len(FEATURES)} campos", divergentes == 0)

    hash_ruim = sum(
        1 for id_leitura, linha in gravadas.iterrows()
        if hash_leitura(Leitura.de_dict({c: linha[c] for c in FEATURES}), int(linha["id_equipamento"]),
                        linha["data_hora"], linha["usuario"]) != linha["hash_entrada"]
    )
    v.registrar("D. Lote simulado", "Hash SHA-256 de integridade confere", "100%",
                f"{len(gravadas) - hash_ruim}/{len(gravadas)} conferem", hash_ruim == 0)

    score_divergente = sum(
        1 for _, linha in gravadas.iterrows()
        if abs(calcular_score_risco(["BAIXO", "MEDIO", "ALTO"],
                                    [linha["prob_baixo"], linha["prob_medio"], linha["prob_alto"]],
                                    override_alto=bool(linha["override_aplicado"])) - linha["score_risco"]) > 0.01
    )
    v.registrar("D. Lote simulado", "Score gravado = risco esperado recalculado das probabilidades",
                "0 divergências", f"{score_divergente} divergências", score_divergente == 0)

    com_risco = gravadas["classe_risco"].isin(["MEDIO", "ALTO"])
    alerta_errado = int((com_risco & gravadas["id_alerta"].isna()).sum()
                        + (~com_risco & gravadas["id_alerta"].notna()).sum())
    v.registrar("D. Lote simulado", "Alerta emitido para todo MÉDIO/ALTO e nunca para BAIXO", "0 inconsistências",
                f"{int(com_risco.sum())} alertas esperados, {alerta_errado} inconsistências", alerta_errado == 0)

    amostra = list(aceitos)[:50]
    nao_deterministicos = sum(
        1 for id_leitura in amostra
        if abs(ctx.servico.avaliar(aceitos[id_leitura])[1].score_risco - gravadas.loc[id_leitura, "score_risco"]) > 1e-9
    )
    v.registrar("D. Lote simulado", "Reavaliar a mesma entrada gera o mesmo score (reprodutível)",
                "0 divergências", f"{nao_deterministicos} em {len(amostra)} reavaliações", nao_deterministicos == 0)

    return {"enviadas": total, "gravadas": len(aceitos), "invalidas": rej_invalidas, "duplicadas": rej_duplicadas,
            "distribuicao": gravadas["classe_risco"].value_counts().to_dict()}


def e_corrupcao(ctx, v: Verificacoes) -> None:
    print("[E] Corrupção no banco")
    entrada = {"umidade_solo": 18, "declividade": 5, "chuva_24h": 2, "temperatura": 25, "velocidade": 6,
               "idade_maquina": 3, "horas_operacao": 3, "status_operacao": "Colheita"}
    id_leitura = ctx.servico.registrar_leitura(entrada, 1, "validacao", origem="validacao-corrupcao")
    with ctx.repo.conexao() as conn:
        conn.execute("UPDATE leituras SET velocidade = 19.5 WHERE id_leitura = ?", (id_leitura,))
    try:
        ctx.servico.processar_leitura(id_leitura)
        obtido, ok = "processada mesmo alterada", False
    except ErroProcessamento:
        linha = ctx.repo.obter_leitura(id_leitura)
        obtido = f"status {linha['status_processamento']}: {linha['erro_processamento'][:70]}"
        ok = linha["status_processamento"] == "ERRO"
    v.registrar("E. Corrupção", "Leitura alterada no banco depois de gravada", "recusada, marcada como ERRO",
                obtido, ok)


def f_oracle(ctx, v: Verificacoes) -> None:
    print("[F] Consistência SQLite x Oracle")
    capturados = []

    class Cursor:
        def var(self, _):
            return mock.Mock(getvalue=mock.Mock(return_value=[len(capturados) + 1]))

        def execute(self, sql, params):
            if "INSERT INTO predicoes" in sql:
                capturados.append(params)

    gravadas = ctx.repo.consultar(
        "SELECT * FROM vw_predicoes WHERE origem = 'validacao-lote' ORDER BY id_predicao LIMIT 100")
    divergentes = 0
    for _, linha in gravadas.iterrows():
        leitura, avaliacao = ctx.servico.avaliar({c: linha[c] for c in FEATURES})
        oracle.inserir(Cursor(), leitura, avaliacao, int(linha["id_equipamento"]), 1, "NUMBER")
        enviado = capturados[-1]
        if abs(enviado["score"] - linha["score_risco"]) > 1e-9 or enviado["classe"] != linha["classe_risco"] \
                or enviado["versao"] != linha["versao_modelo"]:
            divergentes += 1
    v.registrar("F. Oracle", "Mesmo score, classe e versão nas duas persistências", "0 divergências",
                f"{divergentes} em {len(gravadas)} predições", divergentes == 0 and len(gravadas) > 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validação da integração com as fontes de dados")
    parser.add_argument("--leituras", type=int, default=500)
    parser.add_argument("--sem-rede", action="store_true")
    args = parser.parse_args()

    v = Verificacoes()
    with tempfile.TemporaryDirectory() as pasta:
        ctx = criar_contexto(db_path=Path(pasta) / "validacao.db", com_oracle=False)
        inicio = time.perf_counter()
        real = a_fonte_real(ctx, v, args.sem_rede)
        b_falhas_da_fonte(v)
        c_gps(v)
        lote = d_lote_simulado(ctx, v, args.leituras)
        e_corrupcao(ctx, v)
        f_oracle(ctx, v)
        duracao = time.perf_counter() - inicio
        modelo = ctx.servico.modelo
        encerrar_logging()

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    resumo = "todas as verificações passaram" if not v.falhas else f"{v.falhas} verificação(ões) falharam"
    texto = [
        "# Evidência — validação da integração com as fontes de dados",
        "",
        f"> Gerado por `scripts/validar_integracao.py` em {datetime.now():%d/%m/%Y %H:%M} · modelo "
        f"{modelo.versao} (`{modelo.hash_arquivo}`) · {args.leituras} leituras simuladas · {duracao:.0f}s · "
        f"banco SQLite temporário (o banco real não é alterado).",
        "",
        f"**Resultado: {resumo}.**",
        "",
        "## Verificações",
        "",
        tabela_markdown(pd.DataFrame(v.linhas)),
        "",
        "## A. Clima real consultado (Open-Meteo)",
        "",
        tabela_markdown(real) if not real.empty else "_Consulta real não executada ou indisponível._",
        "",
        "## D. Lote de telemetria simulada",
        "",
        f"- Leituras enviadas: **{lote['enviadas']}** (≈5% com problema injetado e ≈3% retransmitidas)",
        f"- Gravadas e avaliadas: **{lote['gravadas']}** · rejeitadas por validação: **{lote['invalidas']}** · "
        f"rejeitadas como duplicata: **{lote['duplicadas']}**",
        f"- Distribuição das classes gravadas: {lote['distribuicao']}",
        "",
        "## Como reproduzir",
        "",
        "```bash",
        f"python scripts/validar_integracao.py --leituras {args.leituras}",
        "```",
    ]
    SAIDA.write_text("\n".join(texto) + "\n", encoding="utf-8")
    print(f"\n{resumo.capitalize()}. Evidência: {SAIDA.relative_to(RAIZ)}")
    sys.exit(1 if v.falhas else 0)


if __name__ == "__main__":
    main()
