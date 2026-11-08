# FASE7 — Jupyter local com PyTorch e GPU

Os sete notebooks estão preparados para Windows/Jupyter. CSV, WAV, TXT, ZIP e XLSX continuam como dados de entrada. A implementação PyTorch do app RNN também está disponível em células editáveis no notebook.

## Abrir neste PC

O ambiente isolado `.venv` já está instalado com Python 3.14, PyTorch 2.11.0+cu128 e as dependências. A partir da pasta FIAP:

```powershell
ANO1/FASE7/.venv/Scripts/python.exe -m jupyterlab ANO1/FASE7
```

Escolha o kernel **Python (FASE7)** e execute as células em ordem. Como alternativa, execute `iniciar_jupyter.ps1`. Reinicie o kernel ao alternar entre notebooks.

## Recriar o ambiente

A partir de FIAP:

```powershell
python -m venv ANO1/FASE7/.venv
ANO1/FASE7/.venv/Scripts/python.exe -m pip install --upgrade pip
ANO1/FASE7/.venv/Scripts/python.exe -m pip install torch==2.11.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu128
ANO1/FASE7/.venv/Scripts/python.exe -m pip install -r ANO1/FASE7/requirements-local.txt
ANO1/FASE7/.venv/Scripts/python.exe -m ipykernel install --prefix ANO1/FASE7/.venv --name fase7 --display-name "Python (FASE7)"
```

Instale esses comandos em ordem. A RTX 5060 Ti detectada tem 16 GB e utiliza a build CUDA 12.8. Não é preciso instalar o CUDA Toolkit separadamente para as wheels oficiais. Referências: https://pytorch.org/get-started/locally/ e https://pytorch.org/get-started/previous-versions/.

Verifique CUDA:

```powershell
ANO1/FASE7/.venv/Scripts/python.exe -c "import torch; print(torch.__version__, torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

Se retornar `False`, confira a build CUDA e o kernel selecionado. Os notebooks permitem execução em CPU quando CUDA não está disponível.

## Áudio e interação

FFmpeg é disponibilizado automaticamente pelo pacote `imageio-ffmpeg`, em `.tools`, quando não está no PATH. Não é necessária instalação global.

O notebook Cap 03 grava cinco segundos pelo microfone padrão do Windows usando sounddevice. Permita acesso ao microfone nas configurações de privacidade. A conversa repetida é opcional (`CONVERSAR = True`). A captura exige o kernel rodando no próprio PC.

gTTS e Google SpeechRecognition precisam de internet. Whisper executa localmente e baixa os pesos na primeira execução. Os dados IMDB, B2W e Machado estão em `RNN/data`. Gradio abre em `127.0.0.1`, sem túnel público. Encerre com `app.close()` ou `app_voz.close()`.

## Alterações e validação

- Séries temporais: LSTMs PyTorch, modelos e lotes na GPU; previsões convertidas para NumPy. Datas das ações ordenadas cronologicamente.
- Multivariada: leitura de datas compatível com pandas atual, normalização ajustada somente no treino e RMSE também na unidade original.
- RNN: BiLSTMs IMDB/B2W, laboratório de gradientes e geração por caracteres com PyTorch. Os treinos completos podem levar vários minutos.
- Voz: Whisper usa CUDA/FP16 na GPU e FP32 na CPU. Silero e processamento de sinais permanecem em CPU.
- Texto: classificadores scikit-learn usam CPU; o exemplo de representação densa agora aprende features com NMF, em vez de usar vetores de zeros.
- Cap 04: algoritmo genético NumPy, sem treino neural que justifique migração para GPU.

A primeira célula localiza FASE7 e muda para a pasta dos dados. Saídas antigas foram removidas. Consulte `VALIDACAO_LOCAL.md` para os testes executados e suas limitações.
