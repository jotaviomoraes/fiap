"""Serviço Oracle da Fase 3: garante a tabela e executa as consultas dos sensores.

Uso (a partir da raiz do projeto, com as credenciais no .env):
    python src/fase3_banco_oracle/servico_oracle.py

O DDL e as consultas vêm de consultas.sql, a mesma fonte usada no SQL Developer.
O CSV só é importado com a tabela vazia, e nenhum dado existente é apagado.
"""

import csv
import os
import re
import sys
from pathlib import Path

import oracledb
from dotenv import load_dotenv

PASTA_BASE = Path(__file__).resolve().parent
ARQUIVO_SQL = PASTA_BASE / "consultas.sql"
ARQUIVO_CSV = PASTA_BASE / "sensores_agricolas.csv"

TABELA = "FARMSENSORES_AGRICOLAS"
COLUNAS = (
    "n", "p", "k", "temperatura", "umidade", "ph", "chuva", "cultura", "irrigacao"
)
TEMPO_CONEXAO = 15  # segundos


def ler_sql(caminho=ARQUIVO_SQL):
    """Separa o DDL e as consultas numeradas do arquivo .sql."""
    texto = caminho.read_text(encoding="utf-8")
    ddl = re.search(r"CREATE TABLE.*?\);", texto, re.DOTALL).group(0).rstrip(";")
    consultas = [
        (titulo.strip(), sql.strip())
        for titulo, sql in re.findall(
            r"^--\s*\d+\.\s*(.+?)\n(SELECT[^;]+);", texto, re.MULTILINE
        )
    ]
    return ddl, consultas


def ler_csv(caminho=ARQUIVO_CSV):
    """Converte as linhas do CSV para os tipos das colunas da tabela."""
    with open(caminho, newline="", encoding="utf-8") as arquivo:
        return [
            (
                int(linha["N"]),
                int(linha["P"]),
                int(linha["K"]),
                float(linha["temperatura"]),
                float(linha["umidade"]),
                float(linha["ph"]),
                float(linha["chuva"]),
                linha["cultura"],
                linha["irrigacao"],
            )
            for linha in csv.DictReader(arquivo)
        ]


def conectar():
    """Abre a conexão com as credenciais do .env da raiz do projeto."""
    load_dotenv(PASTA_BASE.parents[1] / ".env")
    usuario = os.getenv("ORACLE_USER")
    senha = os.getenv("ORACLE_PASSWORD")
    dsn = os.getenv("ORACLE_DSN", "oracle.fiap.com.br:1521/orcl")
    if not usuario or not senha:
        raise SystemExit("Preencha ORACLE_USER e ORACLE_PASSWORD no arquivo .env.")
    return oracledb.connect(
        user=usuario, password=senha, dsn=dsn, tcp_connect_timeout=TEMPO_CONEXAO
    )


def garantir_tabela(cursor, ddl):
    """Cria a tabela somente se ela ainda não existir."""
    cursor.execute(
        "SELECT COUNT(*) FROM user_tables WHERE table_name = :1", [TABELA]
    )
    if cursor.fetchone()[0]:
        print(f"Tabela {TABELA} encontrada.")
        return
    cursor.execute(ddl)
    print(f"Tabela {TABELA} criada.")


def importar_se_vazia(cursor, linhas):
    """Importa o CSV somente com a tabela vazia e devolve o total de registros."""
    cursor.execute(f"SELECT COUNT(*) FROM {TABELA}")
    total = cursor.fetchone()[0]
    if total:
        print(f"Tabela com {total} registros. Importação do CSV ignorada.")
        return total

    marcadores = ", ".join(f":{i}" for i in range(1, len(COLUNAS) + 1))
    cursor.executemany(
        f"INSERT INTO {TABELA} ({', '.join(COLUNAS)}) VALUES ({marcadores})",
        linhas,
    )
    print(f"{len(linhas)} registros importados de {ARQUIVO_CSV.name}.")
    return len(linhas)


def formatar_tabela(colunas, linhas):
    """Monta um texto com as colunas alinhadas."""
    celulas = [[str(valor) for valor in linha] for linha in linhas]
    larguras = [
        max([len(coluna)] + [len(linha[i]) for linha in celulas])
        for i, coluna in enumerate(colunas)
    ]

    def montar_linha(valores):
        return " | ".join(v.ljust(largura) for v, largura in zip(valores, larguras))

    saida = [montar_linha(colunas)]
    saida.append("-+-".join("-" * largura for largura in larguras))
    saida += [montar_linha(linha) for linha in celulas]
    return "\n".join(saida)


def executar_consultas(cursor, consultas):
    """Executa as consultas e imprime o resultado de cada uma."""
    for numero, (titulo, sql) in enumerate(consultas, start=1):
        cursor.execute(sql)
        colunas = [coluna[0].lower() for coluna in cursor.description]
        linhas = cursor.fetchall()
        print(f"\n{numero}. {titulo}")
        print(f"Registros retornados: {len(linhas)}")
        if linhas:
            print(formatar_tabela(colunas, linhas))


def main():
    print("=== FarmTech Solutions - Serviço Oracle (Fase 3) ===")
    ddl, consultas = ler_sql()
    try:
        conexao = conectar()
    except oracledb.Error as erro:
        print(f"Não foi possível conectar ao Oracle: {erro}")
        sys.exit(1)

    with conexao:
        cursor = conexao.cursor()
        try:
            garantir_tabela(cursor, ddl)
            importar_se_vazia(cursor, ler_csv())
            conexao.commit()
            executar_consultas(cursor, consultas)
        except oracledb.Error as erro:
            conexao.rollback()
            print(f"Erro no banco de dados: {erro}")
            sys.exit(1)


if __name__ == "__main__":
    main()
