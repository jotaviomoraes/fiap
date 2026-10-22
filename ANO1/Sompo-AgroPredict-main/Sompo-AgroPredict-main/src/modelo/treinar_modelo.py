"""
treinar_modelo.py
-----------------
Treino reproduzivel do modelo final (Sprint 4), do dado bruto ao .pkl.

Etapas:
  1. Qualidade: `agropredict.qualidade.limpar_dataset` trata o dataset bruto
  2. Split estratificado treino/teste (75/25), semente fixa
  3. Comparacao de algoritmos com GridSearchCV (5 folds estratificados):
     Regressao Logistica (baseline), Random Forest e Gradient Boosting
  4. Selecao por criterio explicito (recall de ALTO primeiro, depois F1 macro)
  5. Revisao de variaveis: ablacao de `status_operacao` e importancia por permutacao
  6. Calibracao das probabilidades (o score e calculado a partir delas)
  7. Comparacao com o modelo anterior (v1.0) no mesmo conjunto de teste
  8. Modelo final reajustado com todos os dados limpos e salvo com metadados

Uso (a partir da raiz do repositorio):
    python src/modelo/treinar_modelo.py

Saidas:
    src/modelo/modelo.pkl            pipeline final
    src/modelo/modelo_meta.json      versao, hiperparametros, metricas, qualidade
    document/relatorio_modelo.md     relatorio gerado a partir das metricas
    assets/10..13_*.png              graficos de avaliacao
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import sklearn  # noqa: E402
from sklearn.base import clone  # noqa: E402
from sklearn.calibration import CalibratedClassifierCV, calibration_curve  # noqa: E402
from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.inspection import permutation_importance  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score, brier_score_loss, confusion_matrix, f1_score, log_loss,
    make_scorer, precision_score, recall_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_validate, train_test_split  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from agropredict.entrada import FEATURES, FEATURES_NUMERICAS  # noqa: E402
from agropredict.qualidade import CLASSES, limpar_dataset  # noqa: E402
from agropredict.regras import PESO_RISCO  # noqa: E402

VERSAO = "v2.0"
RANDOM_STATE = 42
DATASET_BRUTO = RAIZ / "src" / "data" / "dataset_v3_bruto.csv"
SAIDA_MODELO = RAIZ / "src" / "modelo" / "modelo.pkl"
SAIDA_META = RAIZ / "src" / "modelo" / "modelo_meta.json"
# Modelo da Sprint 2/3 congelado, usado apenas como referencia de comparacao
MODELO_ANTERIOR = RAIZ / "src" / "modelo" / "modelo_v1.pkl"
SAIDA_RELATORIO = RAIZ / "document" / "relatorio_modelo.md"
ASSETS = RAIZ / "assets"

# Criterio de selecao (explicito): no dominio, deixar de alertar um risco ALTO
# e o erro mais caro. Entre os candidatos com recall de ALTO >= RECALL_ALTO_MINIMO
# na validacao cruzada, vence o de maior F1 macro.
RECALL_ALTO_MINIMO = 0.95
# Revisao de variaveis: uma variavel sai do modelo se remove-la custar menos que isto em F1 macro.
TOLERANCIA_ABLACAO = 0.005

COR_1, COR_2, COR_3 = "#2a78d6", "#eb6834", "#1baf7a"  # paleta categorica em ordem fixa
CV = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
ESCORES = {
    "f1_macro": "f1_macro",
    "recall_alto": make_scorer(recall_score, labels=["ALTO"], average="macro"),
    "accuracy": "accuracy",
}


def preprocessador(usar_status: bool, escalar: bool = False) -> ColumnTransformer:
    numerico = [("imputar", SimpleImputer(strategy="median"))]
    if escalar:
        numerico.append(("escalar", StandardScaler()))
    transformadores = [("num", Pipeline(numerico), FEATURES_NUMERICAS)]
    if usar_status:
        transformadores.append(("cat", Pipeline([
            ("imputar", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]), ["status_operacao"]))
    return ColumnTransformer(transformadores, remainder="drop")


def candidatos(usar_status: bool = True) -> dict:
    return {
        "Regressão Logística (baseline)": (
            Pipeline([("preproc", preprocessador(usar_status, escalar=True)),
                      ("clf", LogisticRegression(max_iter=5000, class_weight="balanced"))]),
            {"clf__C": [0.1, 1.0, 10.0]},
        ),
        "Random Forest": (
            Pipeline([("preproc", preprocessador(usar_status)),
                      ("clf", RandomForestClassifier(n_estimators=300, max_features="sqrt", class_weight="balanced",
                                                     random_state=RANDOM_STATE, n_jobs=-1))]),
            {"clf__max_depth": [None, 10, 16], "clf__min_samples_leaf": [1, 3, 5]},
        ),
        "Gradient Boosting": (
            Pipeline([("preproc", preprocessador(usar_status)),
                      ("clf", HistGradientBoostingClassifier(class_weight="balanced", random_state=RANDOM_STATE))]),
            {"clf__learning_rate": [0.05, 0.1], "clf__max_depth": [None, 6], "clf__max_iter": [300]},
        ),
    }


def score_esperado(probas: np.ndarray, classes) -> np.ndarray:
    pesos = np.array([PESO_RISCO[c] for c in classes])
    return probas @ pesos


def metricas(y_true, y_pred, probas, classes) -> dict:
    y_bin = np.array([[1 if y == c else 0 for c in classes] for y in y_true])
    recall = recall_score(y_true, y_pred, labels=list(CLASSES), average=None, zero_division=0)
    precisao = precision_score(y_true, y_pred, labels=list(CLASSES), average=None, zero_division=0)
    matriz = confusion_matrix(y_true, y_pred, labels=list(CLASSES))
    return {
        "acuracia": round(accuracy_score(y_true, y_pred), 4),
        "f1_macro": round(f1_score(y_true, y_pred, average="macro"), 4),
        "recall": {c: round(float(r), 4) for c, r in zip(CLASSES, recall)},
        "precisao": {c: round(float(p), 4) for c, p in zip(CLASSES, precisao)},
        "log_loss": round(log_loss(y_true, probas, labels=list(classes)), 4),
        "brier_medio": round(float(np.mean([brier_score_loss(y_bin[:, i], probas[:, i])
                                            for i in range(len(classes))])), 4),
        "alto_previsto_como_baixo": int(matriz[2, 0]),
        "matriz_confusao": matriz.tolist(),
    }


def avaliar(modelo, X_test, y_test) -> dict:
    probas = modelo.predict_proba(X_test)
    classes = list(modelo.classes_)
    y_pred = np.array(classes)[probas.argmax(axis=1)]
    return metricas(y_test, y_pred, probas, classes)


def resumo_cv(resultado: dict) -> dict:
    return {nome: {"media": round(float(np.mean(resultado[f"test_{nome}"])), 4),
                   "desvio": round(float(np.std(resultado[f"test_{nome}"])), 4)} for nome in ESCORES}


def grafico_comparacao(tabela: pd.DataFrame, destino: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    y = np.arange(len(tabela))
    ax.barh(y - 0.2, tabela["f1_macro_cv"], height=0.36, color=COR_1, label="F1 macro (CV)")
    ax.barh(y + 0.2, tabela["recall_alto_cv"], height=0.36, color=COR_2, label="Recall ALTO (CV)")
    for i, (f1, rec) in enumerate(zip(tabela["f1_macro_cv"], tabela["recall_alto_cv"])):
        ax.text(f1 + 0.003, i - 0.2, f"{f1:.3f}", va="center", fontsize=9)
        ax.text(rec + 0.003, i + 0.2, f"{rec:.3f}", va="center", fontsize=9)
    ax.set_yticks(y, tabela.index)
    ax.set_xlim(min(0.8, tabela[["f1_macro_cv", "recall_alto_cv"]].min().min() - 0.02), 1.02)
    # Limiar na legenda (e nao como texto solto) para nao sobrepor o titulo
    ax.axvline(RECALL_ALTO_MINIMO, color="#777", linestyle="--", linewidth=1,
               label=f"Recall ALTO mínimo ({RECALL_ALTO_MINIMO:.2f})")
    ax.set_title("Comparação de algoritmos — validação cruzada (5 folds)", pad=12)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=3, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(destino, dpi=110)
    plt.close(fig)


def grafico_matriz(matriz: list[list[int]], titulo: str, destino: Path) -> None:
    fig, ax = plt.subplots(figsize=(5.2, 4.4))
    dados = np.array(matriz)
    ax.imshow(dados, cmap="Blues")
    for i in range(3):
        for j in range(3):
            ax.text(j, i, dados[i, j], ha="center", va="center",
                    color="white" if dados[i, j] > dados.max() * 0.5 else "#1a1a19", fontsize=12)
    ax.set_xticks(range(3), CLASSES)
    ax.set_yticks(range(3), CLASSES)
    ax.set_xlabel("Predito")
    ax.set_ylabel("Real")
    ax.set_title(titulo)
    fig.tight_layout()
    fig.savefig(destino, dpi=110)
    plt.close(fig)


def grafico_importancia(importancias: pd.DataFrame, destino: Path) -> None:
    dados = importancias.sort_values("importancia")
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(dados["variavel"], dados["importancia"], xerr=dados["desvio"], color=COR_1,
            error_kw={"ecolor": "#555", "capsize": 3})
    ax.set_xlabel("Queda no F1 macro ao embaralhar a variável (teste)")
    ax.set_title("Importância por permutação — modelo final")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(destino, dpi=110)
    plt.close(fig)


def grafico_calibracao(curvas: dict, destino: Path) -> None:
    fig, ax = plt.subplots(figsize=(5.6, 5))
    ax.plot([0, 1], [0, 1], linestyle="--", color="#999", linewidth=1, label="calibração perfeita")
    for (nome, (prob_pred, prob_real)), cor in zip(curvas.items(), (COR_2, COR_1)):
        ax.plot(prob_pred, prob_real, marker="o", markersize=5, linewidth=2, color=cor, label=nome)
    ax.set_xlabel("Probabilidade prevista de ALTO")
    ax.set_ylabel("Frequência real de ALTO")
    ax.set_title("Calibração da probabilidade de ALTO (teste)")
    ax.legend(frameon=False, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(destino, dpi=110)
    plt.close(fig)


def definir_n_jobs(modelo, n_jobs: int = 1) -> None:
    """O modelo em producao avalia uma leitura por vez: uma thread basta."""
    estimadores = [modelo] + [c.estimator for c in getattr(modelo, "calibrated_classifiers_", [])]
    if hasattr(modelo, "estimator"):
        estimadores.append(modelo.estimator)
    for est in estimadores:
        for passo in getattr(est, "named_steps", {}).values():
            if "n_jobs" in passo.get_params():
                passo.set_params(n_jobs=n_jobs)


def main() -> None:
    warnings.filterwarnings("ignore", category=UserWarning)
    inicio = time.time()
    print("=" * 64)
    print(f"Sompo AgroPredict — treino do modelo {VERSAO}")
    print("=" * 64)

    # 1. Qualidade -------------------------------------------------------
    bruto = pd.read_csv(DATASET_BRUTO)
    df, qualidade = limpar_dataset(bruto)
    print(f"[1] Qualidade: {qualidade.linhas_entrada} linhas brutas -> {qualidade.linhas_saida} aptas")
    X, y = df[FEATURES], df["risco"]

    # 2. Split -------------------------------------------------------------
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, stratify=y, random_state=RANDOM_STATE)
    print(f"[2] Split estratificado: {len(X_train)} treino / {len(X_test)} teste")

    # 3. Comparacao de algoritmos -----------------------------------------
    resultados = {}
    for nome, (pipeline, grade) in candidatos().items():
        busca = GridSearchCV(pipeline, grade, cv=CV, scoring=ESCORES, refit="f1_macro", n_jobs=-1)
        busca.fit(X_train, y_train)
        i = busca.best_index_
        resultados[nome] = {
            "busca": busca,
            "melhores_parametros": {k.replace("clf__", ""): v for k, v in busca.best_params_.items()},
            "f1_macro_cv": round(float(busca.cv_results_["mean_test_f1_macro"][i]), 4),
            "recall_alto_cv": round(float(busca.cv_results_["mean_test_recall_alto"][i]), 4),
            "acuracia_cv": round(float(busca.cv_results_["mean_test_accuracy"][i]), 4),
            "combinacoes_testadas": len(busca.cv_results_["params"]),
            "teste": avaliar(busca.best_estimator_, X_test, y_test),
        }
        r = resultados[nome]
        print(f"[3] {nome:32} F1 CV={r['f1_macro_cv']:.4f}  recall ALTO CV={r['recall_alto_cv']:.4f}  "
              f"params={r['melhores_parametros']}")

    tabela = pd.DataFrame({n: {k: r[k] for k in ("f1_macro_cv", "recall_alto_cv", "acuracia_cv")}
                           for n, r in resultados.items()}).T

    # 4. Selecao ------------------------------------------------------------
    aptos = tabela[tabela["recall_alto_cv"] >= RECALL_ALTO_MINIMO]
    base = aptos if not aptos.empty else tabela
    escolhido = base["f1_macro_cv"].idxmax()
    print(f"[4] Selecionado: {escolhido}")
    melhor = resultados[escolhido]["busca"].best_estimator_

    # 5. Revisao de variaveis: ablacao de status_operacao --------------------
    params = resultados[escolhido]["busca"].best_params_
    pipe_sem_status = candidatos(usar_status=False)[escolhido][0].set_params(**params)
    cv_com = resumo_cv(cross_validate(melhor, X_train, y_train, cv=CV, scoring=ESCORES, n_jobs=-1))
    cv_sem = resumo_cv(cross_validate(pipe_sem_status, X_train, y_train, cv=CV, scoring=ESCORES, n_jobs=-1))
    perda = cv_com["f1_macro"]["media"] - cv_sem["f1_macro"]["media"]
    usar_status = perda >= TOLERANCIA_ABLACAO
    print(f"[5] Ablação status_operacao: F1 com={cv_com['f1_macro']['media']:.4f} "
          f"sem={cv_sem['f1_macro']['media']:.4f} -> {'mantida' if usar_status else 'removida'}")
    base_final = melhor if usar_status else pipe_sem_status.fit(X_train, y_train)

    # 6. Calibracao ------------------------------------------------------------
    calibrado = CalibratedClassifierCV(base_final, method="isotonic", cv=CV).fit(X_train, y_train)
    teste_base = avaliar(base_final, X_test, y_test)
    teste_cal = avaliar(calibrado, X_test, y_test)
    # Calibrar so compensa se as DUAS medidas de qualidade de probabilidade melhorarem
    # sem perder recall de ALTO; com evidencia mista, fica o modelo mais simples.
    usar_calibracao = (teste_cal["log_loss"] < teste_base["log_loss"]
                       and teste_cal["brier_medio"] < teste_base["brier_medio"]
                       and teste_cal["recall"]["ALTO"] >= teste_base["recall"]["ALTO"] - 0.01)
    final_treino = calibrado if usar_calibracao else base_final
    teste_final = teste_cal if usar_calibracao else teste_base
    print(f"[6] Calibração isotônica: log loss {teste_base['log_loss']:.4f} -> {teste_cal['log_loss']:.4f}, "
          f"Brier {teste_base['brier_medio']:.4f} -> {teste_cal['brier_medio']:.4f} "
          f"-> {'aplicada' if usar_calibracao else 'não aplicada'}")

    curvas = {}
    for nome, mod in (("sem calibração", base_final), ("com calibração isotônica", calibrado)):
        prob = mod.predict_proba(X_test)[:, list(mod.classes_).index("ALTO")]
        real, prev = calibration_curve((y_test == "ALTO").astype(int), prob, n_bins=8, strategy="quantile")
        curvas[nome] = (prev, real)

    # Importancia por permutacao no teste
    perm = permutation_importance(final_treino, X_test, y_test, scoring="f1_macro", n_repeats=10,
                                  random_state=RANDOM_STATE, n_jobs=-1)
    importancias = pd.DataFrame({"variavel": FEATURES, "importancia": perm.importances_mean,
                                 "desvio": perm.importances_std}).sort_values("importancia", ascending=False)
    if not usar_status:
        importancias = importancias[importancias["variavel"] != "status_operacao"]

    # 7. Comparacao com o modelo anterior -------------------------------------
    anterior = None
    if MODELO_ANTERIOR.exists():
        try:
            modelo_v1 = joblib.load(MODELO_ANTERIOR)
            X_test_v1 = X_test.copy()
            X_test_v1[FEATURES_NUMERICAS] = X_test_v1[FEATURES_NUMERICAS].fillna(X_train[FEATURES_NUMERICAS].median())
            X_test_v1["status_operacao"] = X_test_v1["status_operacao"].fillna("Colheita")
            anterior = {"versao": "v1.0", "teste": avaliar(modelo_v1, X_test_v1, y_test)}
            print(f"[7] Modelo anterior {anterior['versao']}: F1={anterior['teste']['f1_macro']:.4f} "
                  f"recall ALTO={anterior['teste']['recall']['ALTO']:.4f} (mesmo teste)")
        except Exception as exc:  # modelo anterior incompatível não impede o treino
            print(f"[7] Modelo anterior não pôde ser avaliado: {exc}")

    # 8. Modelo final com todos os dados --------------------------------------
    config_final = CalibratedClassifierCV(
        (melhor if usar_status else pipe_sem_status), method="isotonic", cv=CV
    ) if usar_calibracao else (melhor if usar_status else pipe_sem_status)
    final = clone(config_final).fit(X, y)
    definir_n_jobs(final)
    joblib.dump(final, SAIDA_MODELO)

    referencia = df[df["risco"] == "BAIXO"][FEATURES_NUMERICAS].median().round(2).to_dict()
    features_usadas = FEATURES if usar_status else FEATURES_NUMERICAS
    meta = {
        "versao": VERSAO,
        "treinado_em": datetime.now().isoformat(timespec="seconds"),
        "sklearn": sklearn.__version__,
        "algoritmo": escolhido,
        "hiperparametros": resultados[escolhido]["melhores_parametros"],
        "calibracao": "isotonica (CalibratedClassifierCV, 5 folds)" if usar_calibracao else "nenhuma",
        "features_usadas": features_usadas,
        "criterio_selecao": (f"maior F1 macro na validacao cruzada entre os candidatos com recall de ALTO "
                             f">= {RECALL_ALTO_MINIMO}"),
        "dataset": {
            "arquivo": str(DATASET_BRUTO.relative_to(RAIZ)).replace("\\", "/"),
            "sha256": hashlib.sha256(DATASET_BRUTO.read_bytes()).hexdigest()[:16],
            "linhas_brutas": qualidade.linhas_entrada,
            "linhas_limpas": qualidade.linhas_saida,
            "distribuicao": df["risco"].value_counts().to_dict(),
            "treino": len(X_train),
            "teste": len(X_test),
        },
        "qualidade": qualidade.como_dict(),
        "candidatos": {n: {k: r[k] for k in ("melhores_parametros", "combinacoes_testadas", "f1_macro_cv",
                                             "recall_alto_cv", "acuracia_cv", "teste")}
                       for n, r in resultados.items()},
        "revisao_variaveis": {
            "status_operacao": {"f1_cv_com": cv_com["f1_macro"]["media"], "f1_cv_sem": cv_sem["f1_macro"]["media"],
                                "decisao": "mantida" if usar_status else "removida"},
            "tolerancia": TOLERANCIA_ABLACAO,
        },
        "validacao_cruzada": cv_com if usar_status else cv_sem,
        "calibracao_teste": {"sem": {k: teste_base[k] for k in ("log_loss", "brier_medio", "f1_macro")},
                             "com": {k: teste_cal[k] for k in ("log_loss", "brier_medio", "f1_macro")}},
        "metricas_teste": teste_final,
        "modelo_anterior": anterior,
        "importancia_permutacao": importancias.round(4).to_dict("records"),
        "referencia_explicacao": referencia,
    }
    SAIDA_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    grafico_comparacao(tabela, ASSETS / "10_comparacao_modelos.png")
    grafico_matriz(teste_final["matriz_confusao"], f"Matriz de confusão — modelo {VERSAO} (teste)",
                   ASSETS / "11_matriz_confusao_v2.png")
    grafico_importancia(importancias, ASSETS / "12_importancia_permutacao.png")
    grafico_calibracao(curvas, ASSETS / "13_calibracao.png")
    escrever_relatorio(meta, qualidade.como_markdown())

    print(f"[8] Modelo final ({len(X)} linhas) salvo em {SAIDA_MODELO.relative_to(RAIZ)}")
    print(f"    Teste: acurácia={teste_final['acuracia']:.4f}  F1 macro={teste_final['f1_macro']:.4f}  "
          f"recall ALTO={teste_final['recall']['ALTO']:.4f}  ALTO->BAIXO={teste_final['alto_previsto_como_baixo']}")
    print(f"Concluído em {time.time() - inicio:.0f}s")


def _pct(valor: float) -> str:
    return f"{valor * 100:.1f}%"


def escrever_relatorio(meta: dict, qualidade_md: str) -> None:
    t = meta["metricas_teste"]
    linhas = [
        f"# Relatório do modelo {meta['versao']}",
        "",
        f"> Gerado automaticamente por `src/modelo/treinar_modelo.py` em {meta['treinado_em']} "
        f"(scikit-learn {meta['sklearn']}). Não edite à mão: rode o script de novo.",
        "",
        "## 1. Dados e qualidade",
        "",
        f"Dataset bruto `{meta['dataset']['arquivo']}` (simulado, sha256 `{meta['dataset']['sha256']}`), "
        "com problemas de coleta injetados de propósito para exercitar o pipeline de qualidade "
        "(`src/agropredict/qualidade.py`):",
        "",
        qualidade_md,
        "",
        f"Distribuição após a limpeza: {meta['dataset']['distribuicao']}. "
        f"Split estratificado: {meta['dataset']['treino']} treino / {meta['dataset']['teste']} teste.",
        "",
        "## 2. Comparação de algoritmos",
        "",
        "Cada candidato teve os hiperparâmetros ajustados por `GridSearchCV` com validação cruzada "
        "estratificada de 5 folds, só no conjunto de treino.",
        "",
        "| Algoritmo | Melhores hiperparâmetros | F1 macro (CV) | Recall ALTO (CV) | F1 macro (teste) | Recall ALTO (teste) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for nome, c in meta["candidatos"].items():
        destaque = "**" if nome == meta["algoritmo"] else ""
        linhas.append(
            f"| {destaque}{nome}{destaque} | `{c['melhores_parametros']}` | {c['f1_macro_cv']:.4f} | "
            f"{c['recall_alto_cv']:.4f} | {c['teste']['f1_macro']:.4f} | {c['teste']['recall']['ALTO']:.4f} |")
    rv = meta["revisao_variaveis"]["status_operacao"]
    cal = meta["calibracao_teste"]
    linhas += [
        "",
        "![Comparação de algoritmos](../assets/10_comparacao_modelos.png)",
        "",
        f"**Critério de seleção:** {meta['criterio_selecao']}. No seguro agrícola, deixar de alertar um risco "
        "ALTO (falso negativo) é o erro mais caro; entre os modelos que protegem essa classe, o F1 macro "
        "garante equilíbrio também em MÉDIO, a classe mais difícil por ficar entre as outras duas.",
        "",
        f"**Escolhido:** {meta['algoritmo']} — `{meta['hiperparametros']}`.",
        "",
        "## 3. Revisão de variáveis",
        "",
        f"- `status_operacao`: F1 macro na validação cruzada **com** a variável = {rv['f1_cv_com']:.4f}, "
        f"**sem** = {rv['f1_cv_sem']:.4f}. Decisão: **{rv['decisao']}** "
        f"(regra: sai se a perda for menor que {meta['revisao_variaveis']['tolerancia']}). "
        "O tipo de operação continua sendo coletado e usado nos relatórios por tipo de operação.",
        f"- Variáveis usadas pelo modelo final: {', '.join(f'`{f}`' for f in meta['features_usadas'])}.",
        "",
        "Importância por permutação no conjunto de teste (queda do F1 macro ao embaralhar cada variável):",
        "",
        "| Variável | Importância | Desvio |",
        "|---|---:|---:|",
        *[f"| `{i['variavel']}` | {i['importancia']:.4f} | {i['desvio']:.4f} |" for i in meta["importancia_permutacao"]],
        "",
        "![Importância por permutação](../assets/12_importancia_permutacao.png)",
        "",
        "## 4. Calibração das probabilidades",
        "",
        "O score de risco é o risco esperado, `0·P(BAIXO) + 50·P(MÉDIO) + 100·P(ALTO)`; por isso a qualidade "
        "das **probabilidades** importa tanto quanto a classe prevista.",
        "",
        "| | Log loss | Brier médio | F1 macro |",
        "|---|---:|---:|---:|",
        f"| Sem calibração | {cal['sem']['log_loss']:.4f} | {cal['sem']['brier_medio']:.4f} | {cal['sem']['f1_macro']:.4f} |",
        f"| Calibração isotônica | {cal['com']['log_loss']:.4f} | {cal['com']['brier_medio']:.4f} | {cal['com']['f1_macro']:.4f} |",
        "",
        f"Decisão: **{meta['calibracao']}**. Regra: a calibração só é aplicada se reduzir **o log loss e o "
        "Brier** sem perder mais de 1 ponto de recall em ALTO; com evidência mista, fica o modelo mais simples.",
        "",
        "![Calibração](../assets/13_calibracao.png)",
        "",
        "## 5. Desempenho final no conjunto de teste",
        "",
        "| Métrica | Valor |",
        "|---|---:|",
        f"| Acurácia | {_pct(t['acuracia'])} |",
        f"| F1 macro | {_pct(t['f1_macro'])} |",
        *[f"| Recall {c} | {_pct(t['recall'][c])} |" for c in CLASSES],
        *[f"| Precisão {c} | {_pct(t['precisao'][c])} |" for c in CLASSES],
        f"| Log loss | {t['log_loss']:.4f} |",
        f"| ALTO previsto como BAIXO | {t['alto_previsto_como_baixo']} |",
        "",
        "![Matriz de confusão](../assets/11_matriz_confusao_v2.png)",
        "",
    ]
    if meta.get("modelo_anterior"):
        a = meta["modelo_anterior"]["teste"]
        linhas += [
            f"### Comparação com o modelo anterior ({meta['modelo_anterior']['versao']}) no mesmo teste",
            "",
            "| Modelo | Acurácia | F1 macro | Recall ALTO | Recall MÉDIO | Log loss |",
            "|---|---:|---:|---:|---:|---:|",
            f"| {meta['modelo_anterior']['versao']} (Sprint 2/3) | {_pct(a['acuracia'])} | {_pct(a['f1_macro'])} | "
            f"{_pct(a['recall']['ALTO'])} | {_pct(a['recall']['MEDIO'])} | {a['log_loss']:.4f} |",
            f"| **{meta['versao']} (Sprint 4)** | **{_pct(t['acuracia'])}** | **{_pct(t['f1_macro'])}** | "
            f"**{_pct(t['recall']['ALTO'])}** | **{_pct(t['recall']['MEDIO'])}** | **{t['log_loss']:.4f}** |",
            "",
            "> O modelo anterior não trata faltantes; para compará-lo, os faltantes do teste foram "
            "preenchidos com a mediana do treino.",
            "",
        ]
    linhas += [
        "## 6. Limitações",
        "",
        "- As métricas são sobre dados **simulados**: os rótulos seguem regras de domínio, então o modelo "
        "aprende essas regras. Avaliar em dados reais exige histórico de sinistros rotulados.",
        "- O modelo final é reajustado com todas as linhas limpas depois da avaliação; as métricas acima "
        "vêm do modelo treinado só com o conjunto de treino.",
    ]
    SAIDA_RELATORIO.write_text("\n".join(linhas) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
