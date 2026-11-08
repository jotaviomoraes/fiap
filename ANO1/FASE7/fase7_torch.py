"""Rotinas PyTorch compartilhadas pelos notebooks locais da FASE7."""
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
torch.manual_seed(42)

class RegressorLSTM(nn.Module):
    def __init__(self, features, hidden=50, layers=1, dropout=0.0):
        super().__init__()
        self.recurrent = nn.ModuleList([
            nn.LSTM(features if i == 0 else hidden, hidden, batch_first=True)
            for i in range(layers)
        ])
        self.dropout = nn.Dropout(dropout)
        self.output = nn.Linear(hidden, 1)

    def forward(self, x):
        for lstm in self.recurrent:
            x, _ = lstm(x)
            x = self.dropout(x)
        return self.output(x[:, -1])

def treinar(model, X, y, optimizer, criterion, epochs=50, batch_size=72, shuffle=True):
    device = next(model.parameters()).device
    ds = TensorDataset(torch.as_tensor(np.asarray(X), dtype=torch.float32),
                       torch.as_tensor(np.asarray(y), dtype=torch.float32).reshape(-1, 1))
    loader = DataLoader(ds, batch_size=batch_size, shuffle=shuffle,
                        num_workers=0, pin_memory=device.type == "cuda")
    history = {"loss": []}
    for epoch in range(epochs):
        model.train()
        total = 0.0
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
            total += loss.item() * len(xb)
        history["loss"].append(total / len(ds))
        print(f"Época {epoch + 1}/{epochs}: loss={history['loss'][-1]:.6f}")
    return history

@torch.inference_mode()
def prever(model, X, batch_size=512):
    model.eval()
    device = next(model.parameters()).device
    batches = []
    for start in range(0, len(X), batch_size):
        xb = torch.as_tensor(np.asarray(X[start:start + batch_size]), dtype=torch.float32, device=device)
        batches.append(model(xb).cpu().numpy())
    return np.concatenate(batches)

def configurar_ffmpeg():
    """Disponibiliza FFmpeg do pacote imageio-ffmpeg sem instalação global."""
    import os
    import shutil
    from pathlib import Path
    if shutil.which("ffmpeg"):
        return
    import imageio_ffmpeg
    pasta = Path(__file__).resolve().parent / ".tools"
    pasta.mkdir(exist_ok=True)
    destino = pasta / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if not destino.exists():
        shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(), destino)
    os.environ["PATH"] = str(pasta) + os.pathsep + os.environ.get("PATH", "")
