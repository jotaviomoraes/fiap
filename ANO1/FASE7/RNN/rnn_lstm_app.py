"""
RNN/LSTM Interactive App - versão PyTorch para GPU (PyCharm)
===========================================================
Este script substitui o notebook Jupyter do Colab e roda diretamente no PyCharm,
treinando na GPU NVIDIA (CUDA) quando disponível.

Funcionalidades:
1. Análise de sentimento (IMDB inglês + B2W português)
2. Laboratório de memória (vanishing gradient)
3. Geração de texto estilo Machado de Assis
4. Interface web Gradio com 4 abas

Por que PyTorch?
----------------
O TensorFlow não usa GPU no Windows nativo a partir da versão 2.11
(é preciso WSL2). O PyTorch usa CUDA nativamente no Windows, então o
projeto foi portado para PyTorch para aproveitar a sua RTX 5060 Ti.

Para rodar: python rnn_lstm_app.py
"""

# =============================================================================
# IMPORTS E CONFIGURAÇÃO INICIAL
# =============================================================================
import os
import re
import time
import json
import threading
import datetime as dt
import warnings
import zipfile
import html
import urllib.request
import socket
from collections import Counter
from io import BytesIO

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Backend não-interativo para salvar gráficos
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

import torch
import torch.nn as nn
import torch.nn.functional as F

import gradio as gr
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score

warnings.filterwarnings("ignore")

# -----------------------------------------------------------------------------
# DISPOSITIVO: GPU (CUDA) se existir, senão CPU
# -----------------------------------------------------------------------------
def escolher_dispositivo():
    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = True
        try:
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
        except Exception:
            pass
        return torch.device("cuda")
    return torch.device("cpu")


DEVICE = escolher_dispositivo()

# Seeds para reprodutibilidade
SEED = 42
np.random.seed(SEED)
torch.manual_seed(SEED)
if DEVICE.type == "cuda":
    torch.cuda.manual_seed_all(SEED)

plt.rcParams.update({
    "figure.dpi": 100,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

# Cores do app
AZUL, TEAL, AMBAR, VERDE, VERMELHO, CINZA = "#065A82", "#1C7293", "#F59E0B", "#16A34A", "#DC2626", "#9CA3AF"
LOCK = threading.Lock()
TREINO_LOCK = threading.Lock()

# Diretório de dados local
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

if DEVICE.type == "cuda":
    _props = torch.cuda.get_device_properties(0)
    print("=" * 60)
    print(f">>> GPU ATIVA: {_props.name}")
    print(f">>> VRAM: {_props.total_memory / 1e9:.1f} GB · CUDA {torch.version.cuda} · PyTorch {torch.__version__}")
    print("=" * 60)
else:
    print("=" * 60)
    print(">>> Nenhuma GPU CUDA encontrada — treinando na CPU.")
    print("=" * 60)


# =============================================================================
# UTILITÁRIOS
# =============================================================================

def fig_png(fig):
    """Figure -> bytes PNG (seguro em threads do Gradio)."""
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    return buf.getvalue()


def cartao(titulo, corpo, cor=AZUL):
    """Retorna HTML de um card colorido."""
    return f"""<div style="border-left:6px solid {cor};background:#F8FAFC;padding:12px 16px;
        border-radius:8px;margin:6px 0;font-family:Arial,sans-serif;color:#1F2937">
        <div style="font-size:12px;letter-spacing:2px;color:{cor};font-weight:bold">{titulo}</div>
        <div style="font-size:15px;margin-top:4px">{corpo}</div></div>"""


def baixar(nome, url, tentativas=3):
    """Baixa arquivo real com retentativas. Nunca substitui por dados simulados."""
    destino = os.path.join(DATA_DIR, nome)
    if os.path.exists(destino) and os.path.getsize(destino) > 1024:
        print(f"    {nome} já está em {DATA_DIR}")
        return destino

    erro = None
    for k in range(tentativas):
        parcial = destino + ".part"
        try:
            print(f"    baixando {nome} ...")
            urllib.request.urlretrieve(url, parcial)
            os.replace(parcial, destino)
            return destino
        except Exception as e:
            erro = e
            if os.path.exists(parcial):
                try:
                    os.remove(parcial)
                except OSError:
                    pass
            print(f"tentativa {k + 1}/{tentativas} de baixar {nome} falhou: {str(e)[:120]}")
            time.sleep(3 * (k + 1))
    raise RuntimeError(f"Não foi possível baixar {nome} de {url}. Verifique a conexão e rode de novo.") from erro


def porta_livre(preferida=7860, tentativas=20):
    """Devolve a primeira porta TCP livre a partir de `preferida`."""
    for p in range(preferida, preferida + tentativas):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", p))
                return p
            except OSError:
                continue
    return preferida


def pad_sequences(sequencias, maxlen=None, padding="post", truncating="post", value=0):
    """Equivalente a keras.utils.pad_sequences (post/pós por padrão)."""
    if maxlen is None:
        maxlen = max((len(s) for s in sequencias), default=0)
    saida = np.full((len(sequencias), int(maxlen)), value, dtype="int64")
    for i, s in enumerate(sequencias):
        s = list(s)
        if truncating == "post":
            s = s[:maxlen]
        else:
            s = s[-maxlen:] if maxlen else []
        if not s:
            continue
        if padding == "post":
            saida[i, :len(s)] = s
        else:
            saida[i, -len(s):] = s
    return saida


# =============================================================================
# GRÁFICOS AO VIVO
# =============================================================================

class GraficoAoVivo:
    """Redesenha as curvas de treino a cada `a_cada` batches e salva em data/."""
    def __init__(self, titulo, metrica=None, a_cada=10):
        self.titulo, self.metrica, self.a_cada = titulo, metrica, a_cada

    def iniciar(self):
        self.n, self.t0 = 0, time.time()
        self.px, self.loss, self.met = [], [], []
        self.ex, self.vloss, self.vmet = [], [], []
        self.epoca = 0

    def batch(self, loss, met=None):
        self.n += 1
        if self.n % self.a_cada:
            return
        self.px.append(self.n)
        self.loss.append(float(loss))
        if self.metrica:
            self.met.append(float(met) if met is not None else np.nan)
        self._desenhar()

    def fim_epoca(self, val_loss, val_met=None):
        self.epoca += 1
        self.ex.append(self.n)
        self.vloss.append(float(val_loss))
        if self.metrica:
            self.vmet.append(float(val_met) if val_met is not None else np.nan)
        self._desenhar()

    def _desenhar(self):
        fig = Figure(figsize=(11, 3.2))
        axs = fig.subplots(1, 2 if self.metrica else 1)
        axs = np.atleast_1d(axs)
        series = [("loss", self.loss, self.vloss)] + (
            [(self.metrica, self.met, self.vmet)] if self.metrica else [])
        for ax, (nome, tr, va) in zip(axs, series):
            ax.plot(self.px, tr, color=AZUL, lw=2, label="treino")
            if va:
                ax.plot(self.ex, va, "o--", color=AMBAR, lw=2, label="validação")
            ax.set_title(nome)
            ax.set_xlabel("batches")
            ax.grid(alpha=.3)
            ax.legend(loc="best")
            ax.spines[["top", "right"]].set_visible(False)
        fig.suptitle(f"{self.titulo} · época {self.epoca} · {time.time() - self.t0:.0f}s", fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(DATA_DIR, f"live_{self.titulo.replace(' ', '_')}.png"))
        plt.close(fig)


# =============================================================================
# 1. SENTIMENTO - IMDB (INGLÊS)
# =============================================================================

VOCAB_SIZE = 10000
MAX_LEN = 200

URL_IMDB_NPZ = "https://storage.googleapis.com/tensorflow/tf-keras-datasets/imdb.npz"
URL_IMDB_WORDS = "https://storage.googleapis.com/tensorflow/tf-keras-datasets/imdb_word_index.json"


def carregar_imdb(num_words=VOCAB_SIZE):
    """Mesma preparação do keras.datasets.imdb.load_data (start_char=1, index_from=3)."""
    caminho = baixar("imdb.npz", URL_IMDB_NPZ)
    with np.load(caminho, allow_pickle=True) as f:
        x_train, y_train = f["x_train"], f["y_train"]
        x_test, y_test = f["x_test"], f["y_test"]

    rng = np.random.RandomState(113)
    i = np.arange(len(x_train))
    rng.shuffle(i)
    x_train, y_train = x_train[i], y_train[i]
    i = np.arange(len(x_test))
    rng.shuffle(i)
    x_test, y_test = x_test[i], y_test[i]

    x_train = [[1] + [w + 3 for w in x] for x in x_train]
    x_test = [[1] + [w + 3 for w in x] for x in x_test]

    xs = x_train + x_test
    # 0 = padding, 1 = start, 2 = OOV; palavras fora do top `num_words` viram 2
    xs = [[w if (0 <= w < num_words) else 2 for w in x] for x in xs]
    idx = len(x_train)
    return (xs[:idx], np.asarray(y_train)), (xs[idx:], np.asarray(y_test))


print(">>> Carregando IMDB...")
(x_tr, y_tr), (x_te, y_te) = carregar_imdb(VOCAB_SIZE)

with open(baixar("imdb_word_index.json", URL_IMDB_WORDS), encoding="utf-8") as f:
    indice = json.load(f)
indice = {k: (v + 3) for k, v in indice.items()}
indice.update({"<PAD>": 0, "<START>": 1, "<UNK>": 2, "<UNUSED>": 3})
reverso = {v: k for k, v in indice.items()}
decodificar = lambda seq: " ".join(reverso.get(i, "?") for i in seq if i > 1)

# Padding
x_tr = pad_sequences(x_tr, maxlen=MAX_LEN, padding="post", truncating="post")
x_te = pad_sequences(x_te, maxlen=MAX_LEN, padding="post", truncating="post")
print(f"Shape treino: {x_tr.shape} | Shape teste: {x_te.shape}")


def inicializar_lstm_estilo_keras(lstm, hidden, esquece=1.0):
    """Aproxima os defaults do Keras: recorrente ortogonal e viés de esquecimento = 1.

    Isso acelera bastante a convergência em relação à inicialização uniforme padrão.
    """
    with torch.no_grad():
        for camada in range(lstm.num_layers):
            nn.init.orthogonal_(getattr(lstm, f"weight_hh_l{camada}"))
            b_ih = getattr(lstm, f"bias_ih_l{camada}")
            b_hh = getattr(lstm, f"bias_hh_l{camada}")
            b_ih[hidden:2 * hidden] = esquece
            b_hh[hidden:2 * hidden] = 0.0


class BiLSTMSentimento(nn.Module):
    """Embedding -> BiLSTM -> Dropout -> Dense -> Dropout -> 1 logit."""

    def __init__(self, vocab_size, max_len, emb_dim=64, hidden=32, p_drop=0.3):
        super().__init__()
        self.max_len = max_len
        self.embed = nn.Embedding(vocab_size, emb_dim, padding_idx=0)
        nn.init.uniform_(self.embed.weight, -0.05, 0.05)  # default do Keras
        self.lstm = nn.LSTM(emb_dim, hidden, batch_first=True, bidirectional=True)
        inicializar_lstm_estilo_keras(self.lstm, hidden)
        self.drop1 = nn.Dropout(p_drop)
        self.fc1 = nn.Linear(2 * hidden, 32)
        self.drop2 = nn.Dropout(p_drop)
        self.out = nn.Linear(32, 1)

    def forward(self, x):
        # x: (B, T) inteiros; 0 é padding
        comprimentos = (x != 0).sum(dim=1).clamp(min=1).cpu()
        emb = self.embed(x)
        empacotado = nn.utils.rnn.pack_padded_sequence(
            emb, comprimentos, batch_first=True, enforce_sorted=False)
        _, (h, _) = self.lstm(empacotado)
        z = torch.cat([h[0], h[1]], dim=1)  # forward + backward
        z = self.drop1(z)
        z = F.relu(self.fc1(z))
        z = self.drop2(z)
        return self.out(z).squeeze(1)


def bce_pesada(logits, alvos, pesos=None):
    """Binary cross-entropy com pesos por classe (como class_weight do Keras)."""
    perda = F.binary_cross_entropy_with_logits(logits, alvos, reduction="none")
    if pesos is None:
        return perda.mean()
    w = torch.where(alvos > .5, pesos[1], pesos[0])
    return (perda * w).sum() / w.sum()


def treinar_sentimento(modelo, X, y, nome, epocas=3, batch_size=128, pesos=None,
                       a_cada=10, lr=1e-3, val_split=.1):
    modelo.to(DEVICE)
    X = torch.from_numpy(np.asarray(X)).long()
    y = torch.from_numpy(np.asarray(y, dtype="float32"))
    gerador = torch.Generator().manual_seed(42)
    perm = torch.randperm(len(X), generator=gerador)
    n_val = max(1, int(val_split * len(X)))
    X_val, y_val = X[perm[:n_val]], y[perm[:n_val]]
    X_tr, y_tr = X[perm[n_val:]], y[perm[n_val:]]

    otim = torch.optim.Adam(modelo.parameters(), lr=lr)
    graf = GraficoAoVivo(nome, metrica="accuracy", a_cada=a_cada)
    graf.iniciar()

    for ep in range(epocas):
        modelo.train()
        ordem = torch.randperm(len(X_tr), generator=gerador)
        soma, acertos, vistos = 0.0, 0, 0
        for bi in range(0, len(X_tr), batch_size):
            idx = ordem[bi:bi + batch_size]
            xb = X_tr[idx].to(DEVICE, non_blocking=True)
            yb = y_tr[idx].to(DEVICE, non_blocking=True)
            logits = modelo(xb)
            perda = bce_pesada(logits, yb, pesos)
            otim.zero_grad(set_to_none=True)
            perda.backward()
            otim.step()

            b = len(idx)
            acc = ((logits > 0).float() == yb).float().mean().item()
            soma += float(perda) * b
            acertos += int(round(acc * b))
            vistos += b
            graf.batch(float(perda), acc)

        modelo.eval()
        vloss, vacc, nv = 0.0, 0, 0
        with torch.inference_mode():
            for bi in range(0, len(X_val), 1024):
                xb = X_val[bi:bi + 1024].to(DEVICE)
                yb = y_val[bi:bi + 1024].to(DEVICE)
                lg = modelo(xb)
                vloss += float(bce_pesada(lg, yb, pesos)) * len(xb)
                vacc += int(((lg > 0).float() == yb).sum())
                nv += len(xb)

        graf.fim_epoca(vloss / nv, vacc / nv)
        print(f"  época {ep + 1}/{epocas} · loss {soma / vistos:.4f} · acc {acertos / vistos:.1%}"
              f" · val_loss {vloss / nv:.4f} · val_acc {vacc / nv:.1%}")

    modelo.eval()
    return modelo


print("Treinando BiLSTM no IMDB...")
modelo_sent = BiLSTMSentimento(VOCAB_SIZE, MAX_LEN)
treinar_sentimento(modelo_sent, x_tr, y_tr, "BiLSTM no IMDB", epocas=3, batch_size=128, a_cada=8)


@torch.inference_mode()
def prever_probabilidades(modelo, X, batch_size=1024):
    modelo.eval()
    saida = []
    for i in range(0, len(X), batch_size):
        xb = torch.from_numpy(np.asarray(X[i:i + batch_size])).long().to(DEVICE)
        saida.append(torch.sigmoid(modelo(xb)).float().cpu().numpy())
    return np.concatenate(saida) if saida else np.empty(0, "float32")


acc_sent = accuracy_score(y_te, prever_probabilidades(modelo_sent, x_te) > .5)
print(f"Acurácia no teste (IMDB): {acc_sent:.1%}")

# =============================================================================
# FUNÇÕES DE ANÁLISE DE SENTIMENTO (COMPARTILHADAS EN/PT)
# =============================================================================

MODELOS_SENT = {}


def registrar_modelo_sent(idioma, modelo, indice, vocab_size, max_len, regex, acuracia, nome):
    MODELOS_SENT[idioma] = dict(modelo=modelo, indice=indice, vocab_size=vocab_size,
                                max_len=max_len, regex=re.compile(regex),
                                acuracia=acuracia, nome=nome)


def ids_do_texto(texto, idioma="en"):
    M = MODELOS_SENT[idioma]
    palavras, ids = [], []
    for bruto in M["regex"].findall((texto or "").lower()):
        w = bruto.strip("'")
        if not w:
            continue
        i = M["indice"].get(w, M["indice"].get(w.replace("'", ""), 2))
        palavras.append(w)
        ids.append(i if i < M["vocab_size"] else 2)
    return palavras[:M["max_len"] - 1], ids[:M["max_len"] - 1]


def prever_lote(lista_ids, idioma="en"):
    M = MODELOS_SENT[idioma]
    X = pad_sequences([[1] + ids for ids in lista_ids], maxlen=M["max_len"],
                      padding="post", truncating="post")
    with LOCK:
        return prever_probabilidades(M["modelo"], X, batch_size=512)


def analisar(texto, idioma="en"):
    palavras, ids = ids_do_texto(texto, idioma)
    if not ids:
        return None
    n = len(ids)
    lote = [ids] + [ids[:k] for k in range(1, n)] + [ids[:j] + ids[j + 1:] for j in range(n)]
    pr = prever_lote(lote, idioma)
    p = float(pr[0])
    return dict(prob=p, palavras=palavras, ids=ids, idioma=idioma,
                leitura=np.append(pr[1:n], p),
                importancia=p - pr[n:],
                unk=[i == 2 for i in ids])


def html_palavras(res):
    m = max(1e-6, np.abs(res["importancia"]).max())
    spans = []
    for w, imp, unk in zip(res["palavras"], res["importancia"], res["unk"]):
        a = min(1, abs(imp) / m) * .85
        cor = f"rgba(22,163,74,{a:.2f})" if imp > 0 else f"rgba(220,38,38,{a:.2f})"
        estilo = "text-decoration:underline dotted #9CA3AF;color:#6B7280" if unk else ""
        spans.append(f"<span title='Δ={imp:+.3f}' style='background:{cor};padding:2px 4px;margin:1px;"
                     f"border-radius:4px;{estilo}'>{html.escape(w)}</span>")
    return " ".join(spans)


def fig_leitura(res):
    fig = Figure(figsize=(11, 3.4))
    ax = fig.subplots()
    y = res["leitura"]
    x = np.arange(1, len(y) + 1)
    ax.axhline(.5, color=CINZA, ls=":")
    ax.fill_between(x, .5, y, where=y >= .5, color=VERDE, alpha=.25, interpolate=True)
    ax.fill_between(x, .5, y, where=y < .5, color=VERMELHO, alpha=.25, interpolate=True)
    ax.plot(x, y, color=AZUL, lw=2, marker="o", ms=4)
    ax.set_ylim(0, 1)
    ax.set_ylabel("P(positiva)")
    ax.set_title("Leitura progressiva: probabilidade após cada palavra")
    if len(x) <= 40:
        ax.set_xticks(x)
        ax.set_xticklabels(res["palavras"], rotation=60, ha="right", fontsize=9)
    else:
        ax.set_xlabel("palavras lidas")
    ax.grid(alpha=.3)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return fig


def raio_x(texto, idioma="en"):
    res = analisar(texto, idioma)
    p = res["prob"]
    print(f"{'POSITIVA' if p > .5 else 'NEGATIVA'} · P(positiva) = {p:.1%} · {MODELOS_SENT[idioma]['nome']}")
    print(html_palavras(res))
    fig = fig_leitura(res)
    fig.savefig(os.path.join(DATA_DIR, f"raiox_{idioma}.png"))
    plt.close(fig)
    return res


# Registra modelo inglês
registrar_modelo_sent("en", modelo_sent, indice, VOCAB_SIZE, MAX_LEN,
                      r"[a-z0-9']+", acc_sent, "BiLSTM treinada no IMDB (inglês)")


# =============================================================================
# 2. LABORATÓRIO DE MEMÓRIA (VANISHING GRADIENT)
# =============================================================================

def sensibilidade(L=100, ganho_rnn=1.0, vies_esquecimento=1.0, unidades=32, seed=0):
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    x = torch.tensor(rng.normal(0, 1, (8, int(L), 1)).astype("float32"),
                     device=DEVICE, requires_grad=True)

    rnn = nn.RNN(1, unidades, batch_first=True, nonlinearity="tanh").to(DEVICE)
    lstm = nn.LSTM(1, unidades, batch_first=True).to(DEVICE)

    with torch.no_grad():
        nn.init.normal_(rnn.weight_ih_l0, 0., .3)
        nn.init.orthogonal_(rnn.weight_hh_l0, gain=ganho_rnn)
        nn.init.zeros_(rnn.bias_ih_l0)
        nn.init.zeros_(rnn.bias_hh_l0)

        nn.init.normal_(lstm.weight_ih_l0, 0., .3)
        nn.init.orthogonal_(lstm.weight_hh_l0, gain=1.0)
        nn.init.zeros_(lstm.bias_ih_l0)
        nn.init.zeros_(lstm.bias_hh_l0)
        # portão de esquecimento (ordem do PyTorch: input, forget, cell, output)
        lstm.bias_ih_l0[unidades:2 * unidades] = float(vies_esquecimento)

    def grad(modelo):
        if x.grad is not None:
            x.grad = None
        saida, _ = modelo(x)
        saida[:, -1, :].sum().backward()
        return np.abs(x.grad[:, :, 0].detach().cpu().numpy()).mean(0) + 1e-12

    g_rnn, g_lstm = grad(rnn), grad(lstm)
    alcance = lambda g: int((g / g[-1] > 1e-2).sum())

    fig = Figure(figsize=(11, 4))
    ax = fig.subplots()
    t = np.arange(int(L))
    ax.semilogy(t, g_rnn / g_rnn[-1], color=VERMELHO, lw=2.2,
                label=f"SimpleRNN (ganho {ganho_rnn:.2f})")
    ax.semilogy(t, g_lstm / g_lstm[-1], color=VERDE, lw=2.2,
                label=f"LSTM (viés do esquecimento {vies_esquecimento:+.1f})")
    ax.axhline(1e-2, color=CINZA, ls=":")
    ax.text(1, 1.3e-2, "1% do sinal", color=CINZA, fontsize=9)
    ax.set_ylim(1e-8, 10)
    ax.set_xlim(0, L - 1)
    ax.set_xlabel("passo de tempo da entrada (0 = início, direita = fim)")
    ax.set_ylabel("sensibilidade relativa (log)")
    ax.set_title("Quanto cada entrada ainda influencia a saída final?")
    ax.legend(loc="lower right")
    ax.grid(alpha=.3, which="both")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()

    resumo = (f"SimpleRNN: {alcance(g_rnn)} de {int(L)} passos ainda recebem ≥1% do sinal\n"
              f"LSTM:      {alcance(g_lstm)} de {int(L)} passos ainda recebem ≥1% do sinal")
    return fig, resumo


# =============================================================================
# 3. SENTIMENTO EM PORTUGUÊS (B2W)
# =============================================================================

URL_B2W = "https://raw.githubusercontent.com/americanas-tech/b2w-reviews01/main/B2W-Reviews01.csv"

print(">>> Baixando B2W-Reviews01...")
caminho_b2w = baixar("B2W-Reviews01.csv", URL_B2W)

b2w = pd.read_csv(caminho_b2w, usecols=["review_title", "review_text", "overall_rating", "site_category_lv1"],
                  low_memory=False).dropna(subset=["review_text"])
print(f"{len(b2w):,} avaliações com texto")

# Filtrar nota 3 e binarizar
b2w = b2w[b2w["overall_rating"] != 3].copy()
b2w["y"] = (b2w["overall_rating"] >= 4).astype("int32")
b2w["texto"] = b2w["review_text"].str.strip()

# Split 80/20 fixo
perm = np.random.default_rng(42).permutation(len(b2w))
n_teste = int(.2 * len(b2w))
b2w_te, b2w_tr = b2w.iloc[perm[:n_teste]], b2w.iloc[perm[n_teste:]]
print(f"Treino: {len(b2w_tr):,} · Teste: {len(b2w_te):,} · Positivas: {b2w['y'].mean():.1%}")

# Vocabulário PT
REGEX_PT = r"[a-zà-öø-ÿ0-9]+"
tokenizar_pt = lambda t: re.findall(REGEX_PT, str(t).lower())
VOCAB_PT, MAX_LEN_PT = 20000, 120

toks_tr = b2w_tr["texto"].map(tokenizar_pt)
contagem_pt = Counter(w for ts in toks_tr for w in ts)
indice_pt = {"<PAD>": 0, "<START>": 1, "<UNK>": 2, "<UNUSED>": 3}
indice_pt.update({w: i + 4 for i, (w, _) in enumerate(contagem_pt.most_common(VOCAB_PT - 4))})


def codificar_pt(textos):
    return pad_sequences([[1] + [indice_pt.get(w, 2) for w in tokenizar_pt(t)] for t in textos],
                         maxlen=MAX_LEN_PT, padding="post", truncating="post")


xp_tr, xp_te = codificar_pt(b2w_tr["texto"]), codificar_pt(b2w_te["texto"])
yp_tr, yp_te = b2w_tr["y"].values, b2w_te["y"].values

# Baseline TF-IDF
tfidf = TfidfVectorizer(token_pattern=REGEX_PT, ngram_range=(1, 2), min_df=3,
                        max_features=200_000, sublinear_tf=True)
Xtf_tr, Xtf_te = tfidf.fit_transform(b2w_tr["texto"]), tfidf.transform(b2w_te["texto"])
baseline_pt = LogisticRegression(max_iter=2000, class_weight="balanced", C=4).fit(Xtf_tr, yp_tr)
p_base = baseline_pt.predict_proba(Xtf_te)[:, 1]
print(f"Baseline TF-IDF + regressão logística: {accuracy_score(yp_te, p_base > .5):.1%}")

# Modelo BiLSTM PT
modelo_pt = BiLSTMSentimento(VOCAB_PT, MAX_LEN_PT)

pesos = torch.tensor([len(yp_tr) / (2 * max(1, (yp_tr == 0).sum())),
                      len(yp_tr) / (2 * max(1, (yp_tr == 1).sum()))], dtype=torch.float32, device=DEVICE)
print(f"Pesos por classe: negativa = {pesos[0]:.2f} · positiva = {pesos[1]:.2f}")

print("Treinando BiLSTM no B2W (português)...")
treinar_sentimento(modelo_pt, xp_tr, yp_tr, "BiLSTM na B2W (português)",
                   epocas=3, batch_size=256, pesos=pesos, a_cada=20)

p_lstm = prever_probabilidades(modelo_pt, xp_te)
acc_pt = accuracy_score(yp_te, p_lstm > .5)
print(f"Acurácia no teste (B2W): {acc_pt:.1%}")

# Registra modelo português
registrar_modelo_sent("pt", modelo_pt, indice_pt, VOCAB_PT, MAX_LEN_PT,
                      REGEX_PT, acc_pt, "BiLSTM treinada na B2W (português)")

# =============================================================================
# 4. MÁQUINA DE ESCREVER - MACHADO DE ASSIS
# =============================================================================

print(">>> Baixando obras de Machado de Assis...")
URL_MACHADO = "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/machado.zip"
zip_machado = zipfile.ZipFile(baixar("machado.zip", URL_MACHADO))

LIVROS = {
    "Dom Casmurro (1899)": "marm08.txt",
    "Memórias Póstumas de Brás Cubas (1881)": "marm05.txt",
    "Quincas Borba (1891)": "marm07.txt"
}


def ler_romance(arquivo):
    t = zip_machado.read(f"machado/romance/{arquivo}").decode("cp1252")
    t = t.replace("\r", "").replace("\xa0", " ")
    m = re.search(r"\n\s*CAP[IÍ]TULO", t)
    if m:
        t = t[m.start():]
    t = re.sub(r"\n\s*FIM\s*$", "", t.strip())
    paragrafos = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", t)]
    return "\n".join(p for p in paragrafos if p)


textos_livros = {nome: ler_romance(arq) for nome, arq in LIVROS.items()}
corpus = "\n\n".join(textos_livros.values())
chars = sorted(set(corpus))
V_CHAR = len(chars)
c2i = {c: i for i, c in enumerate(chars)}
i2c = np.array(chars)
ids_corpus = np.array([c2i[c] for c in corpus], dtype="int32")

freq = np.bincount(ids_corpus, minlength=V_CHAR) / len(ids_corpus)
BPC_UNIGRAMA = float(-(freq * np.log2(freq + 1e-12)).sum())

print(f"Total: {len(corpus):,} caracteres · {V_CHAR} símbolos distintos "
      f"(unigrama: {BPC_UNIGRAMA:.2f} bits/caractere)")

# Dados para treino
SEQ_CHAR = 100
UNIDADES_CHAR = 512
EPOCAS_CHAR = 40

n_seq = (len(ids_corpus) - 1) // SEQ_CHAR
Xc = ids_corpus[:n_seq * SEQ_CHAR].reshape(n_seq, SEQ_CHAR)
Yc = ids_corpus[1:n_seq * SEQ_CHAR + 1].reshape(n_seq, SEQ_CHAR)
ordem = np.random.default_rng(0).permutation(n_seq)
n_val = int(.05 * n_seq)
Xc_val, Yc_val, Xc_tr, Yc_tr = Xc[ordem[:n_val]], Yc[ordem[:n_val]], Xc[ordem[n_val:]], Yc[ordem[n_val:]]
print(f"{len(Xc_tr):,} trechos de treino · {len(Xc_val):,} de validação")


class LSTMChar(nn.Module):
    """Embedding -> LSTM -> Dense nos logits do próximo caractere."""

    def __init__(self, vocab, emb_dim=64, hidden=UNIDADES_CHAR):
        super().__init__()
        self.embed = nn.Embedding(vocab, emb_dim)
        nn.init.uniform_(self.embed.weight, -0.05, 0.05)  # default do Keras
        self.lstm = nn.LSTM(emb_dim, hidden, batch_first=True)
        inicializar_lstm_estilo_keras(self.lstm, hidden)
        self.fc = nn.Linear(hidden, vocab)

    def forward(self, x, estado=None):
        saida, estado = self.lstm(self.embed(x), estado)
        return self.fc(saida), estado


def treinar_char(modelo, Xtr, Ytr, Xval, Yval, epocas, batch_size=128, paciencia=3,
                 a_cada=10, lr=2e-3):
    modelo.to(DEVICE)
    Xtr = torch.from_numpy(np.asarray(Xtr)).long()
    Ytr = torch.from_numpy(np.asarray(Ytr)).long()
    Xval = torch.from_numpy(np.asarray(Xval)).long()
    Yval = torch.from_numpy(np.asarray(Yval)).long()

    otim = torch.optim.Adam(modelo.parameters(), lr=lr)
    gerador = torch.Generator().manual_seed(0)
    graf = GraficoAoVivo("LSTM de caracteres em Machado de Assis", a_cada=a_cada)
    graf.iniciar()

    melhor, sem_melhora, melhores_pesos = float("inf"), 0, None
    historico = []

    for ep in range(epocas):
        modelo.train()
        ordem = torch.randperm(len(Xtr), generator=gerador)
        soma, vistos = 0.0, 0
        for bi in range(0, len(Xtr), batch_size):
            idx = ordem[bi:bi + batch_size]
            xb = Xtr[idx].to(DEVICE, non_blocking=True)
            yb = Ytr[idx].to(DEVICE, non_blocking=True)
            logits, _ = modelo(xb)
            perda = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), yb.reshape(-1))
            otim.zero_grad(set_to_none=True)
            perda.backward()
            torch.nn.utils.clip_grad_norm_(modelo.parameters(), 1.0)
            otim.step()

            b = len(idx)
            soma += float(perda) * b
            vistos += b
            graf.batch(float(perda))

        modelo.eval()
        vloss, vistos_v = 0.0, 0
        with torch.inference_mode():
            for bi in range(0, len(Xval), 512):
                xb = Xval[bi:bi + 512].to(DEVICE)
                yb = Yval[bi:bi + 512].to(DEVICE)
                logits, _ = modelo(xb)
                vloss += float(F.cross_entropy(logits.reshape(-1, logits.shape[-1]),
                                               yb.reshape(-1), reduction="sum"))
                vistos_v += yb.numel()
        vloss /= vistos_v
        historico.append(vloss)
        graf.fim_epoca(vloss)
        print(f"  época {ep + 1}/{epocas} · loss {soma / vistos:.4f} · val_loss {vloss:.4f}")

        if vloss < melhor - 1e-4:
            melhor, sem_melhora = vloss, 0
            melhores_pesos = {k: v.detach().clone() for k, v in modelo.state_dict().items()}
        else:
            sem_melhora += 1
            if sem_melhora >= paciencia:
                print(f"  early stopping (sem melhora por {paciencia} épocas)")
                break

    if melhores_pesos is not None:
        modelo.load_state_dict(melhores_pesos)
    modelo.eval()
    return historico, melhor


print("Treinando LSTM de caracteres (Machado de Assis)...")
modelo_char = LSTMChar(V_CHAR)
hist_char, melhor_val = treinar_char(modelo_char, Xc_tr, Yc_tr, Xc_val, Yc_val,
                                     EPOCAS_CHAR, batch_size=128)

bpc_char = melhor_val / np.log(2)
print(f"Resultado validação: {bpc_char:.2f} bits/caractere (perplexidade {2 ** bpc_char:.1f})")

# =============================================================================
# FUNÇÕES DE GERAÇÃO DE TEXTO
# =============================================================================

emb_char = modelo_char.embed
lstm_char = modelo_char.lstm
dense_char = modelo_char.fc


def _passo_char(c, h, cc):
    """Um passo da LSTM: c (1,1) inteiro -> logits (1, V), estado novo."""
    with torch.inference_mode():
        saida, (h2, c2) = lstm_char(emb_char(c), (h, cc))
        return dense_char(saida[:, -1, :]), h2, c2


def estado_inicial():
    z = torch.zeros(1, 1, UNIDADES_CHAR, device=DEVICE)
    return z, z


def preparar(prompt):
    """Processa o prompt inteiro de uma vez e devolve estado + logits do próximo char."""
    prompt = "".join(c for c in prompt if c in c2i) or "A"
    with torch.inference_mode():
        ids = torch.tensor([[c2i[c] for c in prompt]], dtype=torch.long, device=DEVICE)
        saida, (h, cc) = lstm_char(emb_char(ids))
        logits = dense_char(saida[:, -1, :])
    return prompt, h, cc, logits


def softmax_T(logits, T):
    z = np.asarray(logits, "float64") / max(T, 1e-3)
    z = np.exp(z - z.max())
    return z / z.sum()


def gerar(prompt="Capitu", n=300, T=0.7, seed=None, guardar_top=0):
    rng = np.random.default_rng(seed)
    prompt, h, cc, logits = preparar(prompt)
    saida, tops = [], []
    with LOCK:
        for _ in range(int(n)):
            p = softmax_T(logits[0].float().cpu().numpy(), T)
            if guardar_top:
                idx = np.argsort(-p)[:guardar_top]
                tops.append([(i2c[i], float(p[i])) for i in idx])
            atual = i2c[rng.choice(len(p), p=p)]
            saida.append(atual)
            c = torch.tensor([[c2i[atual]]], dtype=torch.long, device=DEVICE)
            logits, h, cc = _passo_char(c, h, cc)
    texto = prompt + "".join(saida)
    return (texto, tops) if guardar_top else texto


def html_texto(t):
    return html.escape(t).replace("\n", "<br>")


# Detecção de trechos copiados
def trechos_copiados(texto, minimo=25):
    cobertura = np.zeros(len(texto), bool)
    maiores = []
    i = 0
    while i < len(texto):
        lo, hi = 0, len(texto) - i
        while lo < hi:
            m = (lo + hi + 1) // 2
            if texto[i:i + m] in corpus:
                lo = m
            else:
                hi = m - 1
        if lo >= minimo:
            cobertura[i:i + lo] = True
            maiores.append(texto[i:i + lo])
            i += lo
        else:
            i += 1
    return cobertura, maiores


def html_copia(texto, minimo=25):
    cob, maiores = trechos_copiados(texto, minimo)
    partes, i = [], 0
    while i < len(texto):
        j = i
        while j < len(texto) and cob[j] == cob[i]:
            j += 1
        trecho = html_texto(texto[i:j])
        partes.append(f"<mark style='background:#FDE68A'>{trecho}</mark>" if cob[i] else trecho)
        i = j
    return "".join(partes), cob.mean(), maiores


# Métricas de qualidade do texto gerado
vocab_corpus = set(re.findall(r"\w+", corpus.lower()))


def medidas(texto):
    palavras = re.findall(r"\w+", texto.lower())
    reais = np.mean([w in vocab_corpus for w in palavras]) if palavras else 0
    tri = list(zip(palavras, palavras[1:], palavras[2:]))
    rep = 1 - len(set(tri)) / len(tri) if tri else 0
    return reais, rep


def fig_proximo(prompt, T, k=12):
    prompt, _, _, logits = preparar(prompt)
    p = softmax_T(logits[0].float().cpu().numpy(), T)
    idx = np.argsort(-p)[:k]
    rot = ["␣" if i2c[i] == " " else "↵" if i2c[i] == "\n" else i2c[i] for i in idx]
    H = float(-(p * np.log2(p + 1e-12)).sum())
    fig = Figure(figsize=(11, 3.4))
    ax = fig.subplots()
    ax.bar(range(k), p[idx], color=[VERDE] + [TEAL] * (k - 1))
    ax.set_xticks(range(k))
    ax.set_xticklabels(rot, fontsize=14, family="monospace")
    for i, v in enumerate(p[idx]):
        ax.text(i, v, f"{v:.0%}", ha="center", va="bottom", fontsize=9)
    ax.set_ylim(0, min(1, p[idx].max() * 1.25 + .02))
    ax.set_ylabel("probabilidade")
    ax.set_title(f'Próximo caractere após "…{prompt[-30:]}" · T = {T:.2f} · incerteza = {H:.2f} bits')
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return fig


# =============================================================================
# 5. FUNÇÕES PARA O APP GRADIO
# =============================================================================

MURAL = []
MURAL_LOCK = threading.Lock()
MOSTRAR_TEXTO_NO_MURAL = True
IDIOMAS = {"Português (B2W)": "pt", "Inglês (IMDB)": "en"}


def _registrar(tipo, texto, resultado, prob):
    with MURAL_LOCK:
        MURAL.append((dt.datetime.now().strftime("%H:%M:%S"), tipo, texto.strip()[:140], resultado, prob))
        del MURAL[:-300]


def predizer_sentimento(texto, nome_idioma="Português (B2W)"):
    idioma = IDIOMAS[nome_idioma]
    res = analisar(texto, idioma)
    if res is None:
        return {"Digite uma avaliação": 1.0}, [], None, "Aguardando entrada…"
    p = res["prob"]
    M = MODELOS_SENT[idioma]
    lim = max(.02, .15 * np.abs(res["importancia"]).max())
    destaque = [(w + " ", "positiva" if imp > lim else "negativa" if imp < -lim else None)
                for w, imp in zip(res["palavras"], res["importancia"])]
    top = sorted(zip(res["importancia"], res["palavras"]), key=lambda t: -abs(t[0]))[:3]
    diag = (f"Modelo: {M['nome']} (acurácia no teste {M['acuracia']:.1%})\n"
            f"Probabilidade bruta de positivo: {p:.4f}\n"
            f"Palavras lidas: {len(res['ids'])} | fora do vocabulário (<UNK>): {sum(res['unk'])}\n"
            f"Dispositivo: {DEVICE.type.upper()}"
            + (f" ({torch.cuda.get_device_name(0)})" if DEVICE.type == "cuda" else "")
            + "\nPalavras mais decisivas: " + ", ".join(f"{w} ({d:+.2f})" for d, w in top))
    _registrar("💬 " + idioma, texto, "POSITIVA" if p > .5 else "NEGATIVA", p)
    return {"POSITIVA": p, "NEGATIVA": 1 - p}, destaque, fig_leitura(res), diag


def gerar_machado(prompt, temperatura, tamanho):
    prompt = (prompt or "").strip() or "Capitu"
    fora = sorted(set(c for c in prompt if c not in c2i))
    texto = gerar(prompt, int(tamanho), float(temperatura))
    corpo, frac, maiores = html_copia(texto)
    reais, rep = medidas(texto)
    info = (f"<div style='font-family:Georgia,serif;font-size:15px;line-height:1.6'>{corpo}</div>"
            f"<p style='font-size:12px;color:#6B7280'>T = {float(temperatura):.1f} · "
            f"palavras reais {reais:.0%} · repetição {rep:.0%} · "
            f"<mark style='background:#FDE68A'>copiado do original</mark>: {frac:.0%}"
            + (f" · caracteres ignorados (fora do vocabulário): {html.escape(''.join(fora))}" if fora else "") + "</p>")
    _registrar("✍️ T=" + f"{float(temperatura):.1f}", texto, "GERADO", frac)
    return info, fig_proximo(prompt, float(temperatura))


def estado_mural():
    with MURAL_LOCK:
        dados = list(MURAL)
    sent = [d for d in dados if d[3] != "GERADO"]
    n = len(sent)
    pos = sum(1 for d in sent if d[3] == "POSITIVA")
    ger = len(dados) - n
    pp = pos / n if n else .5
    placar = (f"<div style='font-family:Arial;padding:6px 0'><span style='font-size:28px;font-weight:bold'>{n}</span> "
              f"avaliações testadas · <b style='color:{VERDE}'>{pos} positivas</b> · <b style='color:{VERMELHO}'>{n - pos} negativas</b>"
              f" · <span style='font-size:20px;font-weight:bold'>{ger}</span> textos gerados"
              f"<div style='display:flex;height:22px;border-radius:6px;overflow:hidden;margin-top:8px'>"
              f"<div style='width:{pp*100:.0f}%;background:{VERDE}'></div><div style='flex:1;background:{VERMELHO}'></div></div></div>")
    linhas = [(h, tp, t if MOSTRAR_TEXTO_NO_MURAL else "•••", r, f"{p:.0%}") for h, tp, t, r, p in reversed(dados[-15:])]
    tabela = pd.DataFrame(linhas, columns=["hora", "tipo", "texto", "resultado", "P(pos) / % copiado"])
    return placar, tabela


# =============================================================================
# 6. INTERFACE GRADIO
# =============================================================================

EXEMPLOS_SENT = [
    ["produto excelente, chegou antes do prazo", "Português (B2W)"],
    ["não é ruim, gostei", "Português (B2W)"],
    ["entrega rápida mas o produto é péssimo", "Português (B2W)"],
    ["this is the best movie I have ever seen the acting was incredible", "Inglês (IMDB)"],
    ["the movie was not bad at all", "Inglês (IMDB)"],
    ["great actors but a terrible boring script", "Inglês (IMDB)"],
]
EXEMPLOS_MACHADO = [["Capitu", 0.7, 300], ["Bentinho olhou para", 0.5, 300],
                    ["Ao verme que primeiro roeu", 0.3, 300], ["— Não, senhor", 1.2, 300]]


def criar_app():
    with gr.Blocks(title="LIVE RNN e LSTM | App Interativo") as app:
        gr.Markdown("# 🔁 LIVE: RNN e LSTM em ação\n"
                    f"Modelos treinados **localmente** com dados reais, no dispositivo **{DEVICE.type.upper()}**. Teste no navegador!")

        with gr.Tabs():
            # ABA 1: SENTIMENTO
            with gr.Tab("💬 Sentimento"):
                gr.Markdown("### Duas BiLSTMs: avaliações da B2W (português) e do IMDB (inglês)\n"
                            "O destaque mostra quais palavras empurraram a decisão para cada lado.")
                with gr.Row():
                    with gr.Column(scale=3):
                        sent_lang = gr.Radio(list(IDIOMAS), value="Português (B2W)", label="Modelo")
                        sent_in = gr.Textbox(label="Avaliação", lines=3, placeholder="Escreva uma avaliação...")
                        sent_btn = gr.Button("Analisar sentimento", variant="primary")
                        gr.Examples(examples=EXEMPLOS_SENT, inputs=[sent_in, sent_lang], label="Exemplos para clicar")
                    with gr.Column(scale=2):
                        sent_lbl = gr.Label(label="Resultado", num_top_classes=2)
                        sent_hl = gr.HighlightedText(label="Raio-X das palavras", combine_adjacent=False, show_legend=True,
                                                     color_map={"positiva": VERDE, "negativa": VERMELHO})
                sent_plot = gr.Plot(label="Leitura progressiva")
                sent_diag = gr.Textbox(label="Diagnóstico técnico", lines=5, interactive=False)
                saidas = [sent_lbl, sent_hl, sent_plot, sent_diag]
                sent_btn.click(predizer_sentimento, [sent_in, sent_lang], saidas)
                sent_in.submit(predizer_sentimento, [sent_in, sent_lang], saidas)

            # ABA 2: LABORATÓRIO DE MEMÓRIA
            with gr.Tab("🧠 Lab. de memória"):
                gr.Markdown("### Quanto cada entrada ainda influencia a saída?\n"
                            "Camadas com pesos aleatórios; o gradiente é calculado de verdade com o `autograd` do PyTorch.\n"
                            "**Desafio:** faça a LSTM enxergar a sequência inteira.")
                with gr.Row():
                    lab_L = gr.Slider(20, 300, value=120, step=10, label="Comprimento da sequência")
                    lab_g = gr.Slider(.5, 1.6, value=1.0, step=.05, label="Ganho da matriz recorrente (RNN)")
                    lab_b = gr.Slider(-2, 5, value=1.0, step=.5, label="Viés do portão de esquecimento (LSTM)")
                lab_btn = gr.Button("Calcular", variant="primary")
                lab_plot = gr.Plot(label="Sensibilidade ao longo do tempo")
                lab_txt = gr.Textbox(label="Alcance da memória", lines=2, interactive=False)
                for comp in (lab_L, lab_g, lab_b):
                    comp.release(sensibilidade, [lab_L, lab_g, lab_b], [lab_plot, lab_txt])
                lab_btn.click(sensibilidade, [lab_L, lab_g, lab_b], [lab_plot, lab_txt])

            # ABA 3: MACHADO DE ASSIS
            with gr.Tab("✍️ Machado de Assis"):
                gr.Markdown("### Uma LSTM de caracteres treinada em *Dom Casmurro*, *Brás Cubas* e *Quincas Borba*\n"
                            "Escreva um começo e escolha a temperatura. Trechos em amarelo foram **copiados literalmente** do original.")
                with gr.Row():
                    with gr.Column(scale=1):
                        mach_in = gr.Textbox(label="Começo do texto", value="Capitu")
                        mach_T = gr.Slider(.1, 2.0, value=.7, step=.1, label="Temperatura")
                        mach_n = gr.Slider(50, 600, value=300, step=50, label="Caracteres a gerar")
                        mach_btn = gr.Button("Escrever", variant="primary")
                        gr.Examples(examples=EXEMPLOS_MACHADO, inputs=[mach_in, mach_T, mach_n], label="Sugestões")
                    with gr.Column(scale=2):
                        mach_out = gr.HTML()
                        mach_plot = gr.Plot(label="Distribuição do próximo caractere após o seu começo")
                mach_btn.click(gerar_machado, [mach_in, mach_T, mach_n], [mach_out, mach_plot])

            # ABA 4: MURAL DA TURMA
            with gr.Tab("🏆 Mural da turma"):
                gr.Markdown("### Tudo o que foi testado (atualiza sozinho a cada 5s)")
                mural_placar = gr.HTML()
                mural_tab = gr.Dataframe(interactive=False, wrap=True)
                gr.Timer(5).tick(estado_mural, None, [mural_placar, mural_tab])

        app.load(sensibilidade, [lab_L, lab_g, lab_b], [lab_plot, lab_txt])
        app.load(estado_mural, None, [mural_placar, mural_tab])

        gr.Markdown("---\n**Sobre os modelos:** educacionais, treinados em minutos. "
                    "Sentimento: IMDB (inglês, Maas et al., 2011) e B2W-Reviews01 (português, Real et al., 2019). "
                    "Geração: obra de Machado de Assis em domínio público. "
                    f"Treinamento em **PyTorch {torch.__version__}** no dispositivo **{DEVICE.type.upper()}**.")

    return app


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("RNN/LSTM Interactive App - Iniciando...")
    print("=" * 60)

    # Teste rápido das funções
    print("\n>>> Testando modelos...")
    _ = predizer_sentimento("a beautiful and moving film", "Inglês (IMDB)")
    _ = predizer_sentimento("produto excelente, chegou antes do prazo", "Português (B2W)")
    _ = gerar_machado("Capitu", 0.7, 80)
    with MURAL_LOCK:
        MURAL.clear()
    print("Funções do app OK.")

    # Cria e lança o app
    app = criar_app()
    porta = porta_livre(7860)
    print(f"\n>>> Iniciando interface Gradio em http://localhost:{porta}")
    if porta != 7860:
        print(f">>> (a porta 7860 estava ocupada; use a porta {porta})")
    print(">>> Pressione Ctrl+C para encerrar\n")

    app.queue(default_concurrency_limit=8)
    app.launch(server_name="127.0.0.1", server_port=porta, share=False,
               prevent_thread_lock=False, quiet=False, show_error=True)
