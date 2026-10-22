"""
simular_frota.py
----------------
Popula o SQLite com uma frota simulada passando pelo MESMO fluxo do
dashboard: cada leitura e validada, gravada em `leituras`, lida do banco,
avaliada pelo modelo + regras e gravada em `predicoes`/`alertas`.

Cada regiao tem um perfil climatico e cada operador um estilo de
conducao, para que os relatorios de tendencia e aderencia tenham
diferencas visiveis. Os dados sao ficticios.

Para exercitar a rastreabilidade da coleta, uma pequena fracao das
leituras simula falhas reais: sensor sem valor ou com valor impossivel
(rejeitadas na validacao) e retransmissao identica (rejeitada como
duplicata). Tudo fica registrado na tabela `rejeicoes`.

Uso, a partir da raiz do repositorio:
    python scripts/simular_frota.py                  # 14 dias, 8 leituras/dia/equipamento
    python scripts/simular_frota.py --dias 30 --leituras-por-dia 10
    python scripts/simular_frota.py --limpar         # remove a simulacao anterior antes
    python scripts/simular_frota.py --taxa-falhas 0  # sem falhas de coleta
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agropredict.entrada import FAIXAS_VALIDAS, LeituraInvalida  # noqa: E402
from agropredict.fabrica import criar_contexto  # noqa: E402
from agropredict.servico import LeituraDuplicada  # noqa: E402

ORIGEM = "simulador"

# regiao -> (prob. de chuva no dia, temperatura base °C, declividade base %)
PERFIL_REGIAO = {
    "Sorriso - MT": (0.25, 31, 5),
    "Rio Verde - GO": (0.20, 33, 9),
    "Cascavel - PR": (0.45, 25, 15),
}

# codigo do equipamento -> (operador, excesso de velocidade km/h, prob. de respeitar alerta)
OPERADORES = {
    "COL-01": ("op.carlos", 0.0, 0.90),
    "COL-02": ("op.maria", 1.0, 0.80),
    "TRA-01": ("op.joao", 4.0, 0.45),
    "PUL-01": ("op.ana", 0.5, 0.85),
    "TRA-02": ("op.pedro", 3.0, 0.55),
    "COL-03": ("op.lucia", 0.0, 0.95),
}

VELOCIDADE_POR_STATUS = {"Colheita": 7.0, "Deslocamento": 13.0, "Manobra": 5.0}
FALHAS_SENSOR = (None, 999.0, -50.0)  # sem valor, pico e valor negativo impossivel


def simular_falha(rng, dados: dict) -> dict:
    campo = str(rng.choice(["umidade_solo", "temperatura", "velocidade", "chuva_24h"]))
    return {**dados, campo: FALHAS_SENSOR[int(rng.integers(len(FALHAS_SENSOR)))]}


def _limitar(campo: str, valor: float) -> float:
    minimo, maximo = FAIXAS_VALIDAS[campo]
    return round(float(np.clip(valor, minimo, maximo)), 1)


def gerar_leitura(rng, equipamento: dict, momento: datetime, chuva_dia: float) -> dict:
    prob_chuva, temp_base, decl_base = PERFIL_REGIAO[equipamento["regiao"]]
    _, excesso_vel, _ = OPERADORES[equipamento["codigo"]]
    status = rng.choice(list(VELOCIDADE_POR_STATUS), p=[0.55, 0.25, 0.20])
    hora = momento.hour + momento.minute / 60
    return {
        "chuva_24h": _limitar("chuva_24h", chuva_dia + rng.normal(0, 1.5)),
        "umidade_solo": _limitar("umidade_solo", 16 + chuva_dia * 0.7 + rng.normal(0, 5)),
        # ciclo diario: pico de calor por volta das 14h
        "temperatura": _limitar("temperatura", temp_base + 6 * np.exp(-((hora - 14) ** 2) / 18) + rng.normal(0, 2.5)),
        "declividade": _limitar("declividade", decl_base + rng.normal(0, 4)),
        "velocidade": _limitar("velocidade", VELOCIDADE_POR_STATUS[status] + excesso_vel + rng.normal(0, 2.5)),
        "idade_maquina": float(date.today().year - equipamento["ano_fabricacao"]),
        "horas_operacao": _limitar("horas_operacao", max(0.0, hora - 6) + rng.normal(0, 0.5)),
        "status_operacao": str(status),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador de frota do Sompo AgroPredict")
    parser.add_argument("--dias", type=int, default=14)
    parser.add_argument("--leituras-por-dia", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limpar", action="store_true", help="remove a simulacao anterior")
    parser.add_argument("--taxa-falhas", type=float, default=0.02,
                        help="fracao de leituras com falha de sensor (a metade disso vira retransmissao)")
    args = parser.parse_args()

    simular_frota(criar_contexto(com_oracle=False), args.dias, args.leituras_por_dia,
                  args.seed, args.limpar, args.taxa_falhas)


def simular_frota(ctx, dias: int = 14, leituras_por_dia: int = 8,
                  seed: int = 42, limpar: bool = False, taxa_falhas: float = 0.02) -> int:
    """Gera dados ficticios no contexto informado, sem apagar dados por padrao."""
    rng = np.random.default_rng(seed)
    rng_falhas = np.random.default_rng(seed + 1)  # separado: nao altera a simulacao principal

    if limpar:
        print(f"[INFO] {ctx.repo.remover_por_origem(ORIGEM)} leituras simuladas anteriores removidas")

    equipamentos = ctx.repo.listar_equipamentos().to_dict("records")
    hoje = date.today()
    total, rejeitadas, erros, respondidos = 0, 0, 0, 0

    for delta in range(dias - 1, -1, -1):
        dia = hoje - timedelta(days=delta)
        chuva_regiao = {
            regiao: (rng.gamma(2.0, 12.0) if rng.random() < perfil[0] else rng.uniform(0, 3))
            for regiao, perfil in PERFIL_REGIAO.items()
        }
        for equip in equipamentos:
            operador, _, prob_respeitar = OPERADORES[equip["codigo"]]
            minutos = np.sort(rng.integers(6 * 60, 19 * 60, size=leituras_por_dia))
            for minuto in minutos:
                momento = datetime.combine(dia, datetime.min.time()) + timedelta(minutes=int(minuto))
                if momento > datetime.now():
                    continue
                dados = gerar_leitura(rng, equip, momento, chuva_regiao[equip["regiao"]])
                sorteio = rng_falhas.random()
                if sorteio < taxa_falhas:
                    dados = simular_falha(rng_falhas, dados)
                envios = 2 if taxa_falhas <= sorteio < 1.5 * taxa_falhas else 1
                resultado = None
                for _ in range(envios):
                    try:
                        resultado = ctx.servico.processar(
                            dados, equip["id_equipamento"], operador, origem=ORIGEM,
                            fontes={"umidade": "simulado", "clima": "simulado", "velocidade": "simulado",
                                    "horas": "simulado", "idade": "cadastro"},
                            data_hora=momento.isoformat(sep=" ", timespec="seconds"),
                        )
                        total += 1
                    except (LeituraInvalida, LeituraDuplicada):
                        rejeitadas += 1
                    except Exception as exc:
                        erros += 1
                        print(f"[ERRO] {exc}")
                if resultado is None:
                    continue

                # Alertas de dias anteriores recebem resposta; os de hoje ficam PENDENTES.
                if resultado.id_alerta and delta > 0:
                    acao = "RESPEITOU" if rng.random() < prob_respeitar else "IGNOROU"
                    resposta = momento + timedelta(minutes=int(rng.integers(1, 15)))
                    ctx.repo.registrar_acao_alerta(
                        resultado.id_alerta, acao, operador,
                        data_hora=resposta.isoformat(sep=" ", timespec="seconds"),
                    )
                    respondidos += 1

    print(f"[OK] {total} leituras processadas (entrada -> banco -> modelo -> saida)")
    print(f"[OK] {respondidos} alertas respondidos; alertas de hoje ficaram PENDENTES")
    print(f"[OK] {rejeitadas} entradas recusadas (falha de sensor ou retransmissao), registradas em `rejeicoes`")
    if erros:
        print(f"[AVISO] {erros} erros de processamento")
    print(f"[OK] Banco: {ctx.repo.caminho}")
    if erros:
        raise RuntimeError(f"A simulacao teve {erros} erros de processamento.")
    return total


def popular_demonstracao(ctx) -> int:
    """Popula apenas bancos sem leituras; nunca substitui dados existentes."""
    if not ctx.repo.consultar("SELECT 1 FROM leituras LIMIT 1").empty:
        return 0
    return simular_frota(ctx)


if __name__ == "__main__":
    main()
