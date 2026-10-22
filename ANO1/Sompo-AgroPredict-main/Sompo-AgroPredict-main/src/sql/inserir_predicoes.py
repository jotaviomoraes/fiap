"""
inserir_predicoes.py
--------------------
Script de ingestao das predicoes do modelo no Oracle XE.

Carrega o modelo treinado (modelo.pkl), processa um lote de predicoes
e persiste no banco. Tambem registra alertas para predicoes MEDIO/ALTO.

Score, classe final (com override), recomendacao e probabilidades vem de
`agropredict.avaliacao.avaliar` — a mesma funcao usada pelo dashboard e
pelo SQLite —, entao a mesma entrada gera o mesmo score nos dois bancos.

Uso:
    python inserir_predicoes.py [--n LINHAS] [--modo {batch|exemplo}]

Pre-requisitos:
    - Oracle XE rodando localmente
    - Schema criado (executar schema.sql primeiro)
    - Dependencias: oracledb, joblib, pandas, scikit-learn
    - Variaveis de ambiente: ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN
"""

import argparse
import random
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agropredict import oracle  # noqa: E402
from agropredict.avaliacao import avaliar  # noqa: E402
from agropredict.config import config_oracle  # noqa: E402
from agropredict.entrada import FEATURES, Leitura, LeituraInvalida  # noqa: E402
from agropredict.modelo import ModeloIndisponivel, ModeloRisco  # noqa: E402

# Caminhos relativos ao script
BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = BASE_DIR / "data" / "dataset_v2.csv"

# Equipamentos e operadores existentes no seed de schema.sql
IDS_EQUIPAMENTOS = [1, 2, 3, 4, 5, 6]
IDS_OPERADORES = [1, 2, 3]


# =====================================================================
# Funcoes auxiliares
# =====================================================================
def conectar():
    """Estabelece conexao com o Oracle XE."""
    import oracledb

    config = config_oracle()
    if not oracle.configurado(config):
        print("[ERRO] Defina ORACLE_USER, ORACLE_PASSWORD e ORACLE_DSN.")
        sys.exit(1)
    try:
        conn = oracledb.connect(**config)
        print(f"[OK] Conectado ao Oracle: {config['dsn']}")
        return conn
    except oracledb.DatabaseError as e:
        print(f"[ERRO] Falha na conexao: {e}")
        print("Verifique se o Oracle XE esta rodando e o schema foi criado.")
        sys.exit(1)


def carregar_modelo() -> ModeloRisco:
    """Carrega o modelo treinado a partir do .pkl."""
    try:
        modelo = ModeloRisco.carregar()
    except ModeloIndisponivel as e:
        print(f"[ERRO] {e}")
        sys.exit(1)
    print(f"[OK] Modelo carregado: versao {modelo.versao} ({modelo.hash_arquivo})")
    return modelo


def processar_lote(conn, modelo: ModeloRisco, df: pd.DataFrame, numero_oracle=None,
                   rng: random.Random | None = None) -> dict:
    """Processa um DataFrame e insere todas as predicoes no banco."""
    if numero_oracle is None:
        import oracledb
        numero_oracle = oracledb.NUMBER
    rng = rng or random.Random(42)

    cur = conn.cursor()
    contagem = {"inseridas": 0, "alertas": 0, "rejeitadas": 0}

    for _, row in df[FEATURES].iterrows():
        try:
            leitura = Leitura.de_dict(row.to_dict())
        except LeituraInvalida as e:
            contagem["rejeitadas"] += 1
            print(f"[AVISO] Linha ignorada: {e}")
            continue

        avaliacao = avaliar(modelo, leitura)
        oracle.inserir(
            cur, leitura, avaliacao,
            id_equipamento=rng.choice(IDS_EQUIPAMENTOS),
            id_operador=rng.choice(IDS_OPERADORES),
            numero_oracle=numero_oracle,
        )
        contagem["inseridas"] += 1
        contagem["alertas"] += int(avaliacao.gera_alerta)

    conn.commit()
    cur.close()
    print(f"[OK] {contagem['inseridas']} predicoes inseridas")
    print(f"[OK] {contagem['alertas']} alertas registrados (risco MEDIO/ALTO)")
    if contagem["rejeitadas"]:
        print(f"[AVISO] {contagem['rejeitadas']} linhas rejeitadas na validacao")
    return contagem


def relatorio_apos_ingestao(conn):
    """Imprime um resumo do que foi persistido."""
    cur = conn.cursor()
    print("\n=== Resumo do banco apos ingestao ===")

    cur.execute("SELECT COUNT(*) FROM predicoes")
    print(f"  Total de predicoes: {cur.fetchone()[0]}")

    cur.execute("""
        SELECT classe_risco, COUNT(*)
        FROM predicoes
        GROUP BY classe_risco
        ORDER BY classe_risco
    """)
    print("  Distribuicao por classe:")
    for classe, qtd in cur.fetchall():
        print(f"    {classe:6}: {qtd}")

    cur.execute("SELECT COUNT(*) FROM alertas")
    print(f"  Alertas registrados: {cur.fetchone()[0]}")

    cur.execute("SELECT * FROM vw_metricas_diarias ORDER BY dia DESC FETCH FIRST 5 ROWS ONLY")
    print("\n  Metricas diarias (top 5):")
    for row in cur.fetchall():
        print(f"    {row}")

    cur.close()


# =====================================================================
# Main
# =====================================================================
def main():
    parser = argparse.ArgumentParser(description="Ingestao de predicoes no Oracle XE")
    parser.add_argument("--n", type=int, default=50,
                        help="Numero de linhas do dataset a processar (default: 50)")
    parser.add_argument("--modo", choices=["batch", "exemplo"], default="batch",
                        help="batch: amostra do dataset | exemplo: 3 cenarios fixos")
    args = parser.parse_args()

    print("=" * 60)
    print("Sompo AgroPredict - Ingestao de predicoes no Oracle XE")
    print("=" * 60)

    modelo = carregar_modelo()
    conn = conectar()

    if args.modo == "batch":
        df = pd.read_csv(DATASET_PATH).sample(n=args.n, random_state=42)
        print(f"[INFO] Processando {len(df)} amostras do dataset...")
    else:
        # 3 cenarios fixos para validacao manual
        df = pd.DataFrame([
            {"umidade_solo": 35, "declividade": 5,  "chuva_24h": 2,
             "temperatura": 25, "velocidade": 12, "idade_maquina": 4,
             "horas_operacao": 5,  "status_operacao": "Deslocamento"},
            {"umidade_solo": 65, "declividade": 12, "chuva_24h": 15,
             "temperatura": 33, "velocidade": 16, "idade_maquina": 8,
             "horas_operacao": 9,  "status_operacao": "Colheita"},
            {"umidade_solo": 88, "declividade": 22, "chuva_24h": 50,
             "temperatura": 39, "velocidade": 22, "idade_maquina": 15,
             "horas_operacao": 12, "status_operacao": "Manobra"},
        ])
        print("[INFO] Processando 3 cenarios de exemplo...")

    processar_lote(conn, modelo, df)
    relatorio_apos_ingestao(conn)

    conn.close()
    print("\n[OK] Processo concluido.")


if __name__ == "__main__":
    main()
