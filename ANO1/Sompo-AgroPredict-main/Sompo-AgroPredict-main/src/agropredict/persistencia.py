"""
persistencia.py
---------------
Repositorio SQLite, banco principal do MVP.

A entrada e gravada ANTES do modelo (`leituras`, status PENDENTE). O
servico le a leitura do banco, avalia e grava o resultado (`predicoes`,
`alertas`) na mesma transacao que marca a leitura como PROCESSADA.
Assim o caminho entrada -> banco -> modelo -> saida nao depende da tela.

Evolucao do schema: `SCHEMA` cria a estrutura base e `MIGRACOES` aplica,
em ordem, as mudancas posteriores, controladas por `PRAGMA user_version`.
Um banco antigo e atualizado automaticamente na primeira conexao.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pandas as pd

from .avaliacao import Avaliacao
from .config import DB_PATH
from .entrada import FEATURES_NUMERICAS, Leitura
from .integridade import hash_leitura

SCHEMA = """
CREATE TABLE IF NOT EXISTS equipamentos (
    id_equipamento  INTEGER PRIMARY KEY,
    codigo          TEXT    NOT NULL UNIQUE,
    tipo            TEXT    NOT NULL,
    modelo          TEXT    NOT NULL,
    fabricante      TEXT    NOT NULL,
    ano_fabricacao  INTEGER NOT NULL,
    fazenda         TEXT    NOT NULL,
    regiao          TEXT    NOT NULL,
    ativo           INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario  INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario     TEXT    NOT NULL UNIQUE,
    nome        TEXT,
    perfil      TEXT    NOT NULL
                CHECK (perfil IN ('operador', 'gestor', 'tecnico', 'analista', 'admin')),
    senha_hash  TEXT    NOT NULL,
    ativo       INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
    criado_em   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS leituras (
    id_leitura            INTEGER PRIMARY KEY AUTOINCREMENT,
    data_hora             TEXT    NOT NULL,
    id_equipamento        INTEGER NOT NULL REFERENCES equipamentos (id_equipamento),
    usuario               TEXT    NOT NULL,
    origem                TEXT    NOT NULL,
    umidade_solo          REAL    NOT NULL,
    declividade           REAL    NOT NULL,
    chuva_24h             REAL    NOT NULL,
    temperatura           REAL    NOT NULL,
    velocidade            REAL    NOT NULL,
    idade_maquina         REAL    NOT NULL,
    horas_operacao        REAL    NOT NULL,
    status_operacao       TEXT    NOT NULL
                          CHECK (status_operacao IN ('Colheita', 'Deslocamento', 'Manobra')),
    fonte_umidade         TEXT,
    fonte_clima           TEXT,
    fonte_velocidade      TEXT,
    fonte_horas           TEXT,
    fonte_idade           TEXT,
    latitude              REAL,
    longitude             REAL,
    status_processamento  TEXT    NOT NULL DEFAULT 'PENDENTE'
                          CHECK (status_processamento IN ('PENDENTE', 'PROCESSADA', 'ERRO')),
    erro_processamento    TEXT
);

CREATE TABLE IF NOT EXISTS predicoes (
    id_predicao        INTEGER PRIMARY KEY AUTOINCREMENT,
    id_leitura         INTEGER NOT NULL UNIQUE REFERENCES leituras (id_leitura),
    data_hora          TEXT    NOT NULL,
    classe_modelo      TEXT    NOT NULL CHECK (classe_modelo IN ('BAIXO', 'MEDIO', 'ALTO')),
    classe_risco       TEXT    NOT NULL CHECK (classe_risco IN ('BAIXO', 'MEDIO', 'ALTO')),
    score_risco        REAL    NOT NULL CHECK (score_risco BETWEEN 0 AND 100),
    prob_baixo         REAL    NOT NULL,
    prob_medio         REAL    NOT NULL,
    prob_alto          REAL    NOT NULL,
    override_aplicado  INTEGER NOT NULL CHECK (override_aplicado IN (0, 1)),
    motivo_override    TEXT,
    variaveis_alerta   TEXT,
    recomendacao       TEXT    NOT NULL,
    versao_modelo      TEXT    NOT NULL,
    hash_modelo        TEXT    NOT NULL,
    gravado_oracle     INTEGER NOT NULL DEFAULT 0 CHECK (gravado_oracle IN (0, 1))
);

CREATE TABLE IF NOT EXISTS alertas (
    id_alerta     INTEGER PRIMARY KEY AUTOINCREMENT,
    id_predicao   INTEGER NOT NULL UNIQUE REFERENCES predicoes (id_predicao),
    data_emissao  TEXT    NOT NULL,
    nivel         TEXT    NOT NULL CHECK (nivel IN ('MEDIO', 'ALTO')),
    categoria     TEXT    NOT NULL CHECK (categoria IN ('operacional', 'climatico', 'mecanico')),
    mensagem      TEXT    NOT NULL,
    acao_tomada   TEXT    NOT NULL DEFAULT 'PENDENTE'
                  CHECK (acao_tomada IN ('PENDENTE', 'RESPEITOU', 'IGNOROU')),
    data_acao     TEXT,
    usuario_acao  TEXT,
    observacao    TEXT
);

CREATE TABLE IF NOT EXISTS log_acessos (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    data_hora  TEXT    NOT NULL,
    usuario    TEXT    NOT NULL,
    perfil     TEXT,
    evento     TEXT    NOT NULL,
    sucesso    INTEGER NOT NULL CHECK (sucesso IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_leituras_equip_data ON leituras (id_equipamento, data_hora);
CREATE INDEX IF NOT EXISTS idx_leituras_status     ON leituras (status_processamento);
CREATE INDEX IF NOT EXISTS idx_predicoes_classe    ON predicoes (classe_risco);
CREATE INDEX IF NOT EXISTS idx_alertas_acao        ON alertas (acao_tomada);
CREATE INDEX IF NOT EXISTS idx_log_usuario_data    ON log_acessos (usuario, data_hora);

"""

VIEW_PREDICOES = """
CREATE VIEW vw_predicoes AS
SELECT
    p.id_predicao, l.id_leitura, l.data_hora, l.usuario, l.origem,
    e.id_equipamento, e.codigo AS equipamento, e.tipo AS tipo_equipamento,
    e.modelo, e.fabricante, e.fazenda, e.regiao,
    l.umidade_solo, l.declividade, l.chuva_24h, l.temperatura, l.velocidade,
    l.idade_maquina, l.horas_operacao, l.status_operacao,
    l.fonte_umidade, l.fonte_clima, l.fonte_velocidade, l.fonte_horas, l.fonte_idade,
    l.hash_entrada,
    p.classe_modelo, p.classe_risco, p.score_risco,
    p.prob_baixo, p.prob_medio, p.prob_alto,
    p.override_aplicado, p.motivo_override, p.variaveis_alerta, p.explicacao, p.recomendacao,
    p.versao_modelo, p.hash_modelo, p.gravado_oracle,
    a.id_alerta, a.nivel AS nivel_alerta, a.categoria AS categoria_alerta, a.acao_tomada
FROM predicoes p
JOIN leituras     l ON l.id_leitura     = p.id_leitura
JOIN equipamentos e ON e.id_equipamento = l.id_equipamento
LEFT JOIN alertas a ON a.id_predicao    = p.id_predicao;
"""

# Cada item eleva o `user_version` em 1. Nunca edite uma migracao ja publicada:
# acrescente uma nova ao final.
MIGRACOES = [
    # 1 — Sprint 4: integridade, rejeicoes rastreaveis, explicacao por predicao e visao de relatorios
    """
    ALTER TABLE leituras  ADD COLUMN hash_entrada TEXT;
    ALTER TABLE predicoes ADD COLUMN explicacao   TEXT;
    CREATE INDEX IF NOT EXISTS idx_leituras_hash ON leituras (hash_entrada);

    CREATE TABLE IF NOT EXISTS rejeicoes (
        id_rejeicao     INTEGER PRIMARY KEY AUTOINCREMENT,
        data_hora       TEXT    NOT NULL,
        origem          TEXT    NOT NULL,
        usuario         TEXT,
        id_equipamento  INTEGER,
        tipo            TEXT    NOT NULL CHECK (tipo IN ('INVALIDA', 'DUPLICADA')),
        motivo          TEXT    NOT NULL,
        dados           TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_rejeicoes_data ON rejeicoes (data_hora);

    DROP VIEW IF EXISTS vw_predicoes;
    """ + VIEW_PREDICOES,
]

# Frota ficticia de demonstracao. Os tres primeiros ids coincidem com o
# seed de src/sql/schema.sql para a replicacao Oracle opcional.
EQUIPAMENTOS_SEED = [
    (1, "COL-01", "Colheitadeira", "CR9.90", "New Holland", 2018, "Fazenda Aurora", "Sorriso - MT"),
    (2, "COL-02", "Colheitadeira", "S780", "John Deere", 2020, "Fazenda Aurora", "Sorriso - MT"),
    (3, "TRA-01", "Trator", "7240", "Case IH", 2012, "Fazenda Boa Vista", "Rio Verde - GO"),
    (4, "PUL-01", "Pulverizador", "M4040", "John Deere", 2016, "Fazenda Boa Vista", "Rio Verde - GO"),
    (5, "TRA-02", "Trator", "T7.245", "New Holland", 2009, "Fazenda Santa Clara", "Cascavel - PR"),
    (6, "COL-03", "Colheitadeira", "IDEAL 9T", "Fendt", 2022, "Fazenda Santa Clara", "Cascavel - PR"),
]

ACOES_ALERTA = ("RESPEITOU", "IGNOROU")


def agora_iso() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


class RepositorioSQLite:
    def __init__(self, caminho: Path | str = DB_PATH):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.inicializar()

    @contextmanager
    def conexao(self):
        conn = sqlite3.connect(self.caminho, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def inicializar(self) -> None:
        with self.conexao() as conn:
            conn.executescript(SCHEMA)
            versao = conn.execute("PRAGMA user_version").fetchone()[0]
            for numero, script in enumerate(MIGRACOES[versao:], start=versao + 1):
                conn.executescript(script)
                conn.execute(f"PRAGMA user_version = {numero}")
            conn.executemany(
                """INSERT OR IGNORE INTO equipamentos
                   (id_equipamento, codigo, tipo, modelo, fabricante, ano_fabricacao, fazenda, regiao)
                   VALUES (?,?,?,?,?,?,?,?)""",
                EQUIPAMENTOS_SEED,
            )

    def consultar(self, sql: str, params: tuple | list = ()) -> pd.DataFrame:
        with self.conexao() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    # ------------------------------------------------------------------
    # Equipamentos
    # ------------------------------------------------------------------
    def listar_equipamentos(self, apenas_ativos: bool = True) -> pd.DataFrame:
        filtro = "WHERE ativo = 1" if apenas_ativos else ""
        return self.consultar(f"SELECT * FROM equipamentos {filtro} ORDER BY codigo")

    def obter_equipamento(self, id_equipamento: int) -> dict | None:
        with self.conexao() as conn:
            row = conn.execute(
                "SELECT * FROM equipamentos WHERE id_equipamento = ?", (id_equipamento,)
            ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Leituras (entrada)
    # ------------------------------------------------------------------
    def inserir_leitura(
        self,
        leitura: Leitura,
        id_equipamento: int,
        usuario: str,
        origem: str,
        fontes: dict | None = None,
        posicao: dict | None = None,
        data_hora: str | None = None,
    ) -> int:
        fontes = fontes or {}
        posicao = posicao or {}
        data_hora = data_hora or agora_iso()
        usuario = usuario[:120]
        with self.conexao() as conn:
            cur = conn.execute(
                f"""INSERT INTO leituras (
                        data_hora, id_equipamento, usuario, origem,
                        {", ".join(FEATURES_NUMERICAS)}, status_operacao,
                        fonte_umidade, fonte_clima, fonte_velocidade, fonte_horas, fonte_idade,
                        latitude, longitude, hash_entrada
                    ) VALUES ({", ".join(["?"] * (4 + len(FEATURES_NUMERICAS) + 1 + 8))})""",
                (
                    data_hora, id_equipamento, usuario, origem,
                    *(getattr(leitura, c) for c in FEATURES_NUMERICAS), leitura.status_operacao,
                    fontes.get("umidade"), fontes.get("clima"), fontes.get("velocidade"),
                    fontes.get("horas"), fontes.get("idade"),
                    posicao.get("lat"), posicao.get("lon"),
                    hash_leitura(leitura, id_equipamento, data_hora, usuario),
                ),
            )
            return int(cur.lastrowid)

    def id_leitura_por_hash(self, hash_entrada: str) -> int | None:
        with self.conexao() as conn:
            row = conn.execute(
                "SELECT id_leitura FROM leituras WHERE hash_entrada = ? ORDER BY id_leitura LIMIT 1",
                (hash_entrada,),
            ).fetchone()
        return row[0] if row else None

    def registrar_rejeicao(self, tipo: str, motivo: str, origem: str, usuario: str | None = None,
                           id_equipamento: int | None = None, dados: dict | None = None) -> int:
        """Guarda a entrada recusada (invalida ou duplicada) para rastreabilidade."""
        with self.conexao() as conn:
            cur = conn.execute(
                """INSERT INTO rejeicoes (data_hora, origem, usuario, id_equipamento, tipo, motivo, dados)
                   VALUES (?,?,?,?,?,?,?)""",
                (agora_iso(), origem, usuario[:120] if usuario else None, id_equipamento, tipo, motivo[:500],
                 json.dumps(dados, default=str, ensure_ascii=False)[:2000] if dados is not None else None),
            )
            return int(cur.lastrowid)

    def obter_leitura(self, id_leitura: int) -> dict | None:
        with self.conexao() as conn:
            row = conn.execute("SELECT * FROM leituras WHERE id_leitura = ?", (id_leitura,)).fetchone()
        return dict(row) if row else None

    def ids_leituras_pendentes(self) -> list[int]:
        with self.conexao() as conn:
            rows = conn.execute(
                "SELECT id_leitura FROM leituras WHERE status_processamento = 'PENDENTE' ORDER BY id_leitura"
            ).fetchall()
        return [r[0] for r in rows]

    def marcar_leitura_com_erro(self, id_leitura: int, erro: str) -> None:
        with self.conexao() as conn:
            conn.execute(
                "UPDATE leituras SET status_processamento = 'ERRO', erro_processamento = ? WHERE id_leitura = ?",
                (erro[:500], id_leitura),
            )

    # ------------------------------------------------------------------
    # Predicoes e alertas (saida) — gravados numa unica transacao
    # ------------------------------------------------------------------
    def salvar_resultado(self, id_leitura: int, avaliacao: Avaliacao, data_hora: str) -> tuple[int, int | None]:
        with self.conexao() as conn:
            cur = conn.execute(
                """INSERT INTO predicoes (
                       id_leitura, data_hora, classe_modelo, classe_risco, score_risco,
                       prob_baixo, prob_medio, prob_alto,
                       override_aplicado, motivo_override, variaveis_alerta, explicacao,
                       recomendacao, versao_modelo, hash_modelo
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    id_leitura, data_hora, avaliacao.classe_modelo, avaliacao.classe_risco,
                    avaliacao.score_risco,
                    avaliacao.prob("BAIXO"), avaliacao.prob("MEDIO"), avaliacao.prob("ALTO"),
                    int(avaliacao.override_aplicado), avaliacao.motivo_override,
                    ",".join(avaliacao.variaveis_alerta) or None,
                    json.dumps(avaliacao.explicacao, ensure_ascii=False) if avaliacao.explicacao else None,
                    avaliacao.recomendacao, avaliacao.versao_modelo, avaliacao.hash_modelo,
                ),
            )
            id_predicao = int(cur.lastrowid)

            id_alerta = None
            if avaliacao.gera_alerta:
                cur = conn.execute(
                    """INSERT INTO alertas (id_predicao, data_emissao, nivel, categoria, mensagem)
                       VALUES (?,?,?,?,?)""",
                    (id_predicao, data_hora, avaliacao.classe_risco,
                     avaliacao.categoria_alerta, avaliacao.recomendacao),
                )
                id_alerta = int(cur.lastrowid)

            conn.execute(
                "UPDATE leituras SET status_processamento = 'PROCESSADA', erro_processamento = NULL "
                "WHERE id_leitura = ?",
                (id_leitura,),
            )
        return id_predicao, id_alerta

    def remover_por_origem(self, origem: str) -> int:
        """Apaga leituras de uma origem (ex.: 'simulador') e seus resultados."""
        with self.conexao() as conn:
            subconsulta = "SELECT id_leitura FROM leituras WHERE origem = ?"
            conn.execute("DELETE FROM rejeicoes WHERE origem = ?", (origem,))
            conn.execute(
                f"DELETE FROM alertas WHERE id_predicao IN "
                f"(SELECT id_predicao FROM predicoes WHERE id_leitura IN ({subconsulta}))",
                (origem,),
            )
            conn.execute(f"DELETE FROM predicoes WHERE id_leitura IN ({subconsulta})", (origem,))
            return conn.execute("DELETE FROM leituras WHERE origem = ?", (origem,)).rowcount

    def marcar_gravado_oracle(self, id_predicao: int) -> None:
        with self.conexao() as conn:
            conn.execute("UPDATE predicoes SET gravado_oracle = 1 WHERE id_predicao = ?", (id_predicao,))

    def registrar_acao_alerta(self, id_alerta: int, acao: str, usuario: str, observacao: str | None = None,
                              data_hora: str | None = None) -> bool:
        """Registra a resposta a um alerta pendente. Retorna False se ja respondido."""
        if acao not in ACOES_ALERTA:
            raise ValueError(f"Acao invalida: {acao}")
        with self.conexao() as conn:
            cur = conn.execute(
                """UPDATE alertas
                   SET acao_tomada = ?, data_acao = ?, usuario_acao = ?, observacao = ?
                   WHERE id_alerta = ? AND acao_tomada = 'PENDENTE'""",
                (acao, data_hora or agora_iso(), usuario[:120], (observacao or None) and observacao[:500], id_alerta),
            )
            return cur.rowcount == 1

    # ------------------------------------------------------------------
    # Usuarios e log de acessos
    # ------------------------------------------------------------------
    def obter_usuario(self, usuario: str) -> dict | None:
        with self.conexao() as conn:
            row = conn.execute("SELECT * FROM usuarios WHERE usuario = ?", (usuario,)).fetchone()
        return dict(row) if row else None

    def salvar_usuario(self, usuario: str, senha_hash: str, perfil: str, nome: str | None = None) -> None:
        """Cria o usuario ou atualiza senha, perfil e nome se ele ja existir."""
        with self.conexao() as conn:
            conn.execute(
                """INSERT INTO usuarios (usuario, nome, perfil, senha_hash, criado_em)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT (usuario) DO UPDATE SET
                       senha_hash = excluded.senha_hash,
                       perfil     = excluded.perfil,
                       nome       = COALESCE(excluded.nome, usuarios.nome),
                       ativo      = 1""",
                (usuario, nome, perfil, senha_hash, agora_iso()),
            )

    def definir_usuario_ativo(self, usuario: str, ativo: bool) -> bool:
        with self.conexao() as conn:
            cur = conn.execute("UPDATE usuarios SET ativo = ? WHERE usuario = ?", (int(ativo), usuario))
            return cur.rowcount == 1

    def listar_usuarios(self) -> pd.DataFrame:
        return self.consultar(
            "SELECT usuario, nome, perfil, ativo, criado_em FROM usuarios ORDER BY perfil, usuario"
        )

    def registrar_acesso(self, usuario: str, evento: str, sucesso: bool, perfil: str | None = None) -> None:
        """Registra login, logout, bloqueios e negacoes sem armazenar senhas."""
        with self.conexao() as conn:
            conn.execute(
                "INSERT INTO log_acessos (data_hora, usuario, perfil, evento, sucesso) VALUES (?,?,?,?,?)",
                (agora_iso(), (usuario or "nao_informado")[:120], perfil, evento[:60], int(sucesso)),
            )

    def falhas_login_desde(self, usuario: str, desde: str) -> int:
        with self.conexao() as conn:
            return conn.execute(
                """SELECT COUNT(*) FROM log_acessos
                   WHERE usuario = ? AND evento = 'login' AND sucesso = 0 AND data_hora >= ?""",
                (usuario, desde),
            ).fetchone()[0]
