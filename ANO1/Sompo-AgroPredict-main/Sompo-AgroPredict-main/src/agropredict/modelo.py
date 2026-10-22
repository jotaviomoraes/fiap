"""
modelo.py
---------
Carrega o pipeline scikit-learn serializado e os metadados gerados por
src/modelo/treinar_modelo.py (versao, metricas, importancias, referencia
para explicacao). Cada instancia expoe a versao e o hash SHA-256 do
arquivo, gravados junto de cada predicao para auditoria.

Explicacao local (CA-01.4): para cada variavel numerica, o valor lido e
trocado por um valor de referencia "seguro" (mediana das operacoes BAIXO
no treino) e mede-se quanto o score cai. As variaveis que mais derrubam o
score quando normalizadas sao as que mais pesaram na decisao. Todas as
variacoes sao avaliadas em uma unica chamada ao modelo.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd

from .config import MODELO_META_PATH, MODELO_PATH, VERSAO_MODELO
from .entrada import FEATURES, FEATURES_NUMERICAS, Leitura
from .regras import ALERTA, PESO_RISCO

# Usada so se o modelo nao tiver metadados: metade do limiar de alerta
REFERENCIA_PADRAO = {v: ALERTA[v] / 2 for v in FEATURES_NUMERICAS}


class ModeloIndisponivel(RuntimeError):
    """O arquivo do modelo nao existe ou nao pode ser desserializado."""


@dataclass(frozen=True)
class Contribuicao:
    variavel: str
    valor: float
    referencia: float
    impacto: float  # pontos de score que a variavel acrescenta

    def como_dict(self) -> dict:
        return {"variavel": self.variavel, "valor": self.valor,
                "referencia": self.referencia, "impacto": self.impacto}


class ModeloRisco:
    def __init__(self, pipeline, versao: str, hash_arquivo: str, meta: dict | None = None):
        self.pipeline = pipeline
        self.versao = versao
        self.hash_arquivo = hash_arquivo
        self.meta = meta or {}
        self.classes = [str(c) for c in pipeline.classes_]
        self.referencia = {**REFERENCIA_PADRAO, **self.meta.get("referencia_explicacao", {})}

    @classmethod
    def carregar(cls, caminho: Path = MODELO_PATH, caminho_meta: Path | None = None) -> "ModeloRisco":
        caminho = Path(caminho)
        if not caminho.exists():
            raise ModeloIndisponivel(
                f"Modelo nao encontrado em {caminho}. Execute src/modelo/treinar_modelo.py."
            )
        try:
            conteudo = caminho.read_bytes()
            pipeline = joblib.load(caminho)
        except Exception as exc:  # pickle corrompido ou versao de sklearn incompativel
            raise ModeloIndisponivel(f"Falha ao carregar o modelo {caminho}: {exc}") from exc

        caminho_meta = Path(caminho_meta) if caminho_meta else (
            MODELO_META_PATH if caminho == MODELO_PATH else caminho.with_name(caminho.stem + "_meta.json")
        )
        meta = {}
        if caminho_meta.exists():
            try:
                meta = json.loads(caminho_meta.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise ModeloIndisponivel(f"Metadados do modelo invalidos em {caminho_meta}: {exc}") from exc

        return cls(pipeline, meta.get("versao", VERSAO_MODELO), hashlib.sha256(conteudo).hexdigest()[:12], meta)

    def _scores(self, lote: pd.DataFrame) -> tuple[list[dict[str, float]], list[float]]:
        probas = self.pipeline.predict_proba(lote[FEATURES])
        linhas = [{c: float(p) for c, p in zip(self.classes, linha)} for linha in probas]
        scores = [sum(PESO_RISCO[c] * p for c, p in linha.items()) for linha in linhas]
        return linhas, scores

    def prever(self, leitura: Leitura, top: int = 3) -> tuple[str, dict[str, float], list[Contribuicao]]:
        """Retorna (classe do modelo, {classe: probabilidade}, principais contribuicoes)."""
        base = leitura.como_dict()
        variacoes = [base] + [{**base, v: self.referencia[v]} for v in FEATURES_NUMERICAS]
        probas, scores = self._scores(pd.DataFrame(variacoes))

        probs = probas[0]
        classe = max(probs, key=probs.get)
        contribuicoes = sorted(
            (Contribuicao(v, float(base[v]), float(self.referencia[v]), round(scores[0] - s, 2))
             for v, s in zip(FEATURES_NUMERICAS, scores[1:])),
            key=lambda c: c.impacto, reverse=True,
        )
        return classe, probs, [c for c in contribuicoes[:top] if c.impacto > 0.5]

    def importancias(self) -> pd.DataFrame:
        """Importancia global por permutacao (dos metadados) ou, no modelo legado, a do Random Forest."""
        if self.meta.get("importancia_permutacao"):
            return (pd.DataFrame(self.meta["importancia_permutacao"])
                    .rename(columns={"variavel": "feature"})[["feature", "importancia"]]
                    .sort_values("importancia"))
        clf = self.pipeline.named_steps["clf"]
        preproc = self.pipeline.named_steps["preproc"]
        nomes = FEATURES_NUMERICAS + list(
            preproc.named_transformers_["cat"].get_feature_names_out(["status_operacao"])
        )
        return pd.DataFrame({"feature": nomes, "importancia": clf.feature_importances_}).sort_values("importancia")
