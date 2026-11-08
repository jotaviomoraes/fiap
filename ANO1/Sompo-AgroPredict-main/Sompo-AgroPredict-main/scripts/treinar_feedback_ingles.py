"""Treina offline a BiLSTM IMDB com a codificação do notebook FASE7/RNN."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from torch.utils.data import DataLoader, TensorDataset

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from agropredict.feedback_modelo import BiLSTMSentimento


def main():
    torch.manual_seed(42)
    pasta = RAIZ.parents[1] / "FASE7/RNN/data"
    config = dict(vocab_size=10000, max_len=200, emb_dim=64, hidden=32, p_drop=.3)
    with np.load(pasta / "imdb.npz", allow_pickle=True) as dados:
        xtr, ytr = dados["x_train"], dados["y_train"]
        xte, yte = dados["x_test"], dados["y_test"]
    rng = np.random.RandomState(113)
    for x, y in ((xtr, ytr), (xte, yte)):
        ordem = np.arange(len(x)); rng.shuffle(ordem)
        x[:], y[:] = x[ordem], y[ordem]
    def preparar(sequencias):
        x = torch.zeros((len(sequencias), 200), dtype=torch.long)
        for i, seq in enumerate(sequencias):
            ids = [1] + [int(w) + 3 if int(w) + 3 < 10000 else 2 for w in seq]
            ids = ids[:200]
            x[i, :len(ids)] = torch.tensor(ids)
        return x
    X, Xt = preparar(xtr), preparar(xte)
    tr, val = train_test_split(np.arange(len(X)), test_size=.1, stratify=ytr, random_state=42)
    def loader(x, y, shuffle=False):
        return DataLoader(TensorDataset(x, torch.tensor(y, dtype=torch.float32)),
                          batch_size=128, shuffle=shuffle, num_workers=0)
    treino, validacao, teste = loader(X[tr], ytr[tr], True), loader(X[val], ytr[val]), loader(Xt, yte)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    modelo = BiLSTMSentimento(**config).to(device)
    with torch.no_grad():
        torch.nn.init.uniform_(modelo.embed.weight, -.05, .05)
        modelo.embed.weight[0].zero_()
        for sufixo in ("", "_reverse"):
            torch.nn.init.orthogonal_(getattr(modelo.lstm, "weight_hh_l0" + sufixo))
            for nome in ("bias_ih_l0", "bias_hh_l0"):
                getattr(modelo.lstm, nome + sufixo).zero_()
            getattr(modelo.lstm, "bias_ih_l0" + sufixo)[32:64] = 1
    otim = torch.optim.Adam(modelo.parameters(), lr=.001)
    criterio = torch.nn.BCEWithLogitsLoss()
    @torch.inference_mode()
    def avaliar(batches):
        modelo.eval()
        total, n, probs, ys = 0., 0, [], []
        for x, y in batches:
            x, y = x.to(device), y.to(device)
            logits = modelo(x)
            total += criterio(logits, y).item() * len(x); n += len(x)
            probs.extend(torch.sigmoid(logits).cpu().tolist()); ys.extend(y.cpu().tolist())
        return total / n, np.array(probs), np.array(ys)
    melhor, pesos = float("inf"), None
    print(f"IMDB: {device}, treino={len(tr)}, validação={len(val)}, teste={len(Xt)}", flush=True)
    for epoca in range(3):
        modelo.train()
        total = 0.
        for x, y in treino:
            x, y = x.to(device), y.to(device)
            otim.zero_grad(set_to_none=True)
            loss = criterio(modelo(x), y); loss.backward()
            torch.nn.utils.clip_grad_norm_(modelo.parameters(), 1.)
            otim.step(); total += loss.item() * len(x)
        vloss, _, _ = avaliar(validacao)
        print(f"Época {epoca+1}/3: loss={total/len(tr):.4f}, val_loss={vloss:.4f}", flush=True)
        if vloss < melhor:
            melhor, pesos = vloss, {k: v.detach().cpu().clone() for k, v in modelo.state_dict().items()}
    modelo.load_state_dict(pesos)
    _, probs, y = avaliar(teste)
    indice_bruto = json.loads((pasta / "imdb_word_index.json").read_text(encoding="utf-8"))
    indice = {p: int(i) + 3 for p, i in indice_bruto.items() if int(i) + 3 < 10000}
    indice.update({"<PAD>": 0, "<START>": 1, "<UNK>": 2, "<UNUSED>": 3})
    metricas = dict(acuracia=float(accuracy_score(y, probs > .5)),
                    acuracia_balanceada=float(balanced_accuracy_score(y, probs > .5)),
                    f1_macro=float(f1_score(y, probs > .5, average="macro")),
                    treino=len(tr), validacao=len(val), teste=len(y))
    artefato = dict(formato=1, idioma="en", versao="bilstm-imdb-en-v1", config=config,
                    indice=indice, state_dict=pesos, metricas=metricas, fonte="IMDB / FASE7/RNN",
                    criado_em=datetime.now(timezone.utc).isoformat(), epocas=3,
                    dominio="Avaliações de filmes; sem validação específica no AgroPredict")
    saida = RAIZ / "src/modelo/feedback_bilstm_en.pt"
    torch.save(artefato, saida)
    saida.with_suffix(".json").write_text(json.dumps(
        {k: v for k, v in artefato.items() if k not in {"indice", "state_dict"}},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(metricas, flush=True)


if __name__ == "__main__":
    main()
