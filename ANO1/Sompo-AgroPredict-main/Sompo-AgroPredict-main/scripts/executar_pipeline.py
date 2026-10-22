"""
executar_pipeline.py
--------------------
Executa o fluxo de ponta a ponta do MVP com um unico comando, de forma
reprodutivel (sementes fixas), e atualiza as evidencias da entrega:

  1. (--completo) gera o dataset bruto v3 e treina o modelo final
  2. roda os testes automatizados -> document/evidencias/resultado_testes.txt
  3. popula a frota simulada pelo mesmo fluxo do dashboard
  4. valida a integracao com as fontes de dados -> validacao_integracao.md
  5. gera o relatorio consolidado da frota em data/ (nao versionado)

Uso (a partir da raiz do repositorio):
    python scripts/executar_pipeline.py              # etapas 2 a 5
    python scripts/executar_pipeline.py --completo   # etapas 1 a 5 (retreina o modelo)
    python scripts/executar_pipeline.py --sem-rede   # nao consulta a Open-Meteo real
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
EVIDENCIAS = RAIZ / "document" / "evidencias"


def etapa(titulo: str, comando: list[str], saida_arquivo: Path | None = None, cwd: Path = RAIZ) -> bool:
    print(f"\n{'=' * 70}\n{titulo}\n{'=' * 70}")
    inicio = time.perf_counter()
    ambiente = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    processo = subprocess.run(comando, cwd=cwd, env=ambiente, capture_output=True, text=True, encoding="utf-8")
    saida = processo.stdout + processo.stderr
    print(saida.strip()[-3000:])
    if saida_arquivo:
        saida_arquivo.parent.mkdir(parents=True, exist_ok=True)
        cabecalho = (f"# {titulo}\n# Comando: {' '.join(Path(c).name if i == 0 else c for i, c in enumerate(comando))}"
                     f"\n# Executado em {datetime.now():%d/%m/%Y %H:%M}\n\n")
        saida_arquivo.write_text(cabecalho + saida, encoding="utf-8")
    ok = processo.returncode == 0
    print(f"-> {'OK' if ok else 'FALHOU'} em {time.perf_counter() - inicio:.0f}s")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline de ponta a ponta do Sompo AgroPredict")
    parser.add_argument("--completo", action="store_true", help="regera o dataset e retreina o modelo")
    parser.add_argument("--sem-rede", action="store_true", help="não consulta a Open-Meteo real")
    args = parser.parse_args()
    py = sys.executable

    resultados = {}
    if args.completo:
        resultados["dataset"] = etapa("1a. Dataset bruto v3", [py, "gerar_dataset_v3.py"], cwd=RAIZ / "src" / "data")
        resultados["treino"] = etapa("1b. Treino do modelo final", [py, "src/modelo/treinar_modelo.py"])
    resultados["testes"] = etapa(
        "2. Testes automatizados", [py, "-m", "unittest", "discover", "-s", "tests", "-t", "tests", "-v"],
        EVIDENCIAS / "resultado_testes.txt")
    resultados["simulacao"] = etapa("3. Frota simulada (entrada -> banco -> modelo -> saída)",
                                    [py, "scripts/simular_frota.py", "--limpar"])
    validacao = [py, "scripts/validar_integracao.py"] + (["--sem-rede"] if args.sem_rede else [])
    resultados["validacao"] = etapa("4. Validação da integração", validacao)
    resultados["relatorio"] = etapa("5. Relatório consolidado da frota", [py, "scripts/gerar_relatorio.py"])

    print(f"\n{'=' * 70}\nResumo")
    for nome, ok in resultados.items():
        print(f"  {'OK     ' if ok else 'FALHOU '} {nome}")
    print(f"Evidências em {EVIDENCIAS.relative_to(RAIZ)}")
    sys.exit(0 if all(resultados.values()) else 1)


if __name__ == "__main__":
    main()
