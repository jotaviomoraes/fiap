"""Treino offline da BiLSTM PT do notebook RNN; nunca executado pelo Streamlit."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from torch.nn import functional as F
from torch.utils.data import DataLoader, TensorDataset

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from agropredict.feedback_modelo import BiLSTMSentimento, codificar, tokenizar


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dados", type=Path, default=RAIZ.parents[1] / "FASE7/RNN/data/B2W-Reviews01.csv")
    parser.add_argument("--saida", type=Path, default=RAIZ / "src/modelo/feedback_bilstm.pt")
    parser.add_argument("--epocas", type=int, default=3)
    parser.add_argument("--amostras", type=int, default=30000)
    args = parser.parse_args()
    if args.epocas < 1 or args.amostras < 100:
        parser.error("Use pelo menos uma época e 100 amostras.")
    torch.manual_seed(42)
    np.random.seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    df = pd.read_csv(args.dados, usecols=["review_text", "overall_rating"]).dropna()
    df = df[df.overall_rating.isin([1, 2, 4, 5])].copy()
    # Duplicatas textuais não podem aparecer simultaneamente em treino e teste.
    df["review_text"] = df.review_text.astype(str).str.strip().str.lower()
    df = df[df.review_text.str.len() >= 5].drop_duplicates("review_text")
    df["y"] = (df.overall_rating >= 4).astype(int)
    if len(df) > args.amostras:
        df, _ = train_test_split(df, train_size=args.amostras, stratify=df.y, random_state=42)
    treino, resto = train_test_split(df, test_size=.3, stratify=df.y, random_state=42)
    validacao, teste = train_test_split(resto, test_size=.5, stratify=resto.y, random_state=42)
    frequencias = Counter(p for texto in treino.review_text for p in tokenizar(texto))
    indice = {"<PAD>": 0, "<START>": 1, "<UNK>": 2, "<UNUSED>": 3}
    indice.update({p: i + 4 for i, (p, _) in enumerate(frequencias.most_common(19996))})
    config = {"vocab_size": len(indice), "max_len": 120, "emb_dim": 64, "hidden": 32, "p_drop": .3}
    modelo = BiLSTMSentimento(**config).to(device)
    with torch.no_grad():
        torch.nn.init.uniform_(modelo.embed.weight, -.05, .05)
        torch.nn.init.zeros_(modelo.embed.weight[0])
        for sufixo in ("", "_reverse"):
            torch.nn.init.orthogonal_(getattr(modelo.lstm, "weight_hh_l0" + sufixo))
            for nome in ("bias_ih_l0", "bias_hh_l0"):
                getattr(modelo.lstm, nome + sufixo).zero_()
            getattr(modelo.lstm, "bias_ih_l0" + sufixo)[32:64] = 1
    def loader(frame, shuffle=False):
        ds = TensorDataset(codificar(frame.review_text.tolist(), indice),
                           torch.tensor(frame.y.to_numpy(), dtype=torch.float32))
        return DataLoader(ds, batch_size=256, shuffle=shuffle, num_workers=0,
                          pin_memory=device.type == "cuda")
    train_loader, val_loader, test_loader = loader(treino, True), loader(validacao), loader(teste)
    pesos = torch.tensor([len(treino) / (2 * (treino.y == c).sum()) for c in (0, 1)],
                         dtype=torch.float32, device=device)
    optimizer = torch.optim.Adam(modelo.parameters(), lr=1e-3)
    def perda(logits, alvos):
        w = pesos[alvos.long()]
        return (F.binary_cross_entropy_with_logits(logits, alvos, reduction="none") * w).sum() / w.sum()
    @torch.inference_mode()
    def avaliar(batches):
        modelo.eval()
        total, n, probs, alvos = 0., 0, [], []
        for x, y in batches:
            x, y = x.to(device), y.to(device)
            logits = modelo(x)
            total += perda(logits, y).item() * len(x)
            n += len(x)
            probs.extend(torch.sigmoid(logits).cpu().tolist())
            alvos.extend(y.cpu().tolist())
        return total / n, np.asarray(probs), np.asarray(alvos)
    melhor, pesos_melhores = float("inf"), None
    print(f"Dispositivo: {device} | treino={len(treino)}, validação={len(validacao)}, teste={len(teste)}", flush=True)
    for epoca in range(args.epocas):
        modelo.train()
        total = 0.
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = perda(modelo(x), y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(modelo.parameters(), 1.)
            optimizer.step()
            total += loss.item() * len(x)
        val_loss, _, _ = avaliar(val_loader)
        print(f"Época {epoca+1}/{args.epocas} | loss={total/len(treino):.4f} | val_loss={val_loss:.4f}", flush=True)
        if val_loss < melhor:
            melhor = val_loss
            pesos_melhores = {k: v.detach().cpu().clone() for k, v in modelo.state_dict().items()}
    modelo.load_state_dict(pesos_melhores)
    _, probs, y = avaliar(test_loader)
    metricas = {"acuracia": float(accuracy_score(y, probs >= .5)),
                "acuracia_balanceada": float(balanced_accuracy_score(y, probs >= .5)),
                "f1_macro": float(f1_score(y, probs >= .5, average="macro")),
                "baseline_majoritaria": float(max(y.mean(), 1-y.mean())),
                "treino": len(treino), "validacao": len(validacao), "teste": len(teste)}
    artefato = {"formato": 1, "idioma": "pt", "versao": "bilstm-b2w-pt-v1",
                "config": config, "indice": indice, "state_dict": pesos_melhores,
                "metricas": metricas, "fonte": "B2W-Reviews01 / FASE7/RNN",
                "criado_em": datetime.now(timezone.utc).isoformat(), "epocas": args.epocas,
                "dominio": "Avaliações de produtos; sem validação em feedbacks AgroPredict"}
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    torch.save(artefato, args.saida)
    args.saida.with_suffix(".json").write_text(json.dumps(
        {k: v for k, v in artefato.items() if k not in {"indice", "state_dict"}},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metricas, ensure_ascii=False), flush=True)
    print(f"Modelo salvo em {args.saida}", flush=True)


if __name__ == "__main__":
    main()
