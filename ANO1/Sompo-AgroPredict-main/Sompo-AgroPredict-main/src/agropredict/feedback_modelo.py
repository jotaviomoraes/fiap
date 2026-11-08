"""BiLSTM de sentimento portada do notebook FASE7/RNN, sem treinos no import."""
from __future__ import annotations

import re
import threading
import hashlib
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F

REGEX_PT = r"[a-zà-öø-ÿ0-9]+"


def tokenizar(texto: str, idioma: str = "pt") -> list[str]:
    regex = REGEX_PT if idioma == "pt" else r"[a-z0-9']+"
    return [p for bruto in re.findall(regex, texto.lower()) if (p := bruto.strip("'"))]


class BiLSTMSentimento(nn.Module):
    """Mesma arquitetura do notebook: embedding, BiLSTM, dropout e saída binária."""

    def __init__(self, vocab_size: int, max_len: int = 120, emb_dim: int = 64,
                 hidden: int = 32, p_drop: float = .3):
        super().__init__()
        self.max_len = max_len
        self.embed = nn.Embedding(vocab_size, emb_dim, padding_idx=0)
        self.lstm = nn.LSTM(emb_dim, hidden, batch_first=True, bidirectional=True)
        self.drop1 = nn.Dropout(p_drop)
        self.fc1 = nn.Linear(hidden * 2, 32)
        self.drop2 = nn.Dropout(p_drop)
        self.out = nn.Linear(32, 1)

    def forward(self, x):
        comprimentos = (x != 0).sum(dim=1).clamp(min=1).cpu()
        sequencias = nn.utils.rnn.pack_padded_sequence(
            self.embed(x), comprimentos, batch_first=True, enforce_sorted=False)
        _, (h, _) = self.lstm(sequencias)
        z = self.drop1(torch.cat([h[0], h[1]], dim=1))
        return self.out(self.drop2(F.relu(self.fc1(z)))).squeeze(1)


def codificar(textos, indice: dict[str, int], max_len: int = 120, idioma: str = "pt"):
    saida = torch.zeros((len(textos), max_len), dtype=torch.long)
    for i, texto in enumerate(textos):
        ids = ([1] + [indice.get(p, indice.get(p.replace("'", ""), 2))
                      for p in tokenizar(str(texto), idioma)])[:max_len]
        saida[i, :len(ids)] = torch.tensor(ids)
    return saida


class AnalisadorFeedback:
    def __init__(self, caminho: Path, idioma: str = "pt"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        artefato = torch.load(caminho, map_location="cpu", weights_only=True)
        if idioma not in {"pt", "en"} or artefato.get("formato") != 1 or artefato.get("idioma") != idioma:
            raise ValueError("Artefato de sentimento incompatível.")
        self.idioma = idioma
        self.indice = artefato["indice"]
        self.config = artefato["config"]
        fingerprint = hashlib.sha256(caminho.read_bytes()).hexdigest()[:12]
        self.versao = f"{artefato['versao']}:{fingerprint}"
        self.metricas = artefato["metricas"]
        self.model = BiLSTMSentimento(**self.config).to(self.device)
        self.model.load_state_dict(artefato["state_dict"])
        self.model.eval()
        self.lock = threading.Lock()

    def classificar(self, texto: str) -> dict:
        """Decisão binária do notebook: positivo acima de 0,5; negativo nos demais."""
        todas = tokenizar(texto, self.idioma)
        palavras = todas[:self.config["max_len"] - 1]
        if not palavras:
            raise ValueError("Digite um texto para analisar.")
        ids = [self.indice.get(p, self.indice.get(p.replace("'", ""), 2)) for p in palavras]
        prefixos = torch.zeros((len(ids), self.config["max_len"]), dtype=torch.long)
        for i in range(len(ids)):
            prefixos[i, :i + 2] = torch.tensor([1] + ids[:i + 1])
        sem_palavra = torch.zeros_like(prefixos)
        for i in range(len(ids)):
            restantes = [1] + ids[:i] + ids[i + 1:]
            sem_palavra[i, :len(restantes)] = torch.tensor(restantes)
        with self.lock, torch.inference_mode():
            leitura = []
            for inicio in range(0, len(prefixos), 64):
                x = prefixos[inicio:inicio + 64].to(self.device)
                leitura.extend(torch.sigmoid(self.model(x)).cpu().tolist())
            removidas = []
            for inicio in range(0, len(sem_palavra), 64):
                x = sem_palavra[inicio:inicio + 64].to(self.device)
                removidas.extend(torch.sigmoid(self.model(x)).cpu().tolist())
        p = leitura[-1]
        return {"classificacao": "BOM" if p > .5 else "RUIM",
                "prob_bom": p, "prob_ruim": 1 - p, "versao_modelo": self.versao,
                "idioma": self.idioma, "palavras": palavras, "leitura": leitura,
                "importancia": [p - removida for removida in removidas],
                "unk": [i == 2 for i in ids], "palavras_total": len(todas),
                "modelo": "BiLSTM B2W" if self.idioma == "pt" else "BiLSTM IMDB",
                "acuracia_teste": self.metricas["acuracia"],
                "dispositivo": (f"CUDA ({torch.cuda.get_device_name(self.device)})"
                                if self.device.type == "cuda" else "CPU")}
