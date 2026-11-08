# Validação local — 05/11/2026

Ambiente: Windows, Python 3.14, PyTorch 2.11.0+cu128, NVIDIA GeForce RTX 5060 Ti (16 GB). Kernel Python (FASE7) registrado dentro de .venv.

Verificações concluídas:

- Estrutura nbformat e sintaxe Python das células dos sete notebooks.
- Ausência de imports TensorFlow/Keras, comandos Linux e APIs google.colab nas células executáveis.
- Execução completa de classificação de texto e algoritmo genético.
- Séries univariada e multivariada com dados locais e uma época cada: treino e previsão em CUDA. A configuração normal continua em 100 e 50 épocas.
- Forward/backward e atualização de pesos da BiLSTM; forward/backward da LSTM de caracteres; gradientes do laboratório de memória em CUDA.
- Leitura do WAV fornecido e cálculo de espectrogramas no Cap 03.
- Imports de torch, torchaudio, Gradio, librosa, Whisper e sounddevice.
- FFmpeg portátil disponível em .tools.
- pip check: nenhuma dependência quebrada.

Não foram executados os treinos completos IMDB/B2W/Machado, os serviços externos gTTS/Google STT, download/inferência dos pesos Whisper, gravação pelo microfone ou navegação interativa do Gradio. Os testes CUDA foram curtos e verificam execução, sem certificar a qualidade final dos modelos. O sandbox impediu a gravação do cache de fontes no perfil do usuário, sem impedir os cálculos e gráficos.
