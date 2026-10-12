# Fase 6 — Detecção de Objetos com YOLOv5

## 📌 Sobre o projeto

Este projeto foi desenvolvido como parte da **Fase 6** do curso de Análise de Sistemas e Inteligência Artificial da FIAP.

O objetivo foi desenvolver e avaliar um modelo de **detecção de objetos utilizando YOLOv5**, trabalhando com um conjunto de dados próprio composto por duas classes:

- 🐱 **Gato**
- 👟 **Tênis**

O projeto contempla desde a preparação e anotação do dataset até o treinamento, validação, comparação de diferentes configurações e realização de inferências sobre imagens não utilizadas durante o treinamento.

---

## 👥 Integrantes

| Integrante | RM |
|---|---|
| Renata de Almeida Marinho | RM569346 |
| Pedro Henrique Figueira de Lacerda | RM573114 |
| Giselli Mayumi Takahashi Yokoyama | RM572690 |
| João Otávio Moraes | RM573227 |
| David Ribeiro Prado de Lacerda | RM570350 |

---

## 🎥 Vídeo de apresentação

O vídeo apresenta a proposta do projeto, preparação dos dados, metodologia utilizada, experimentos realizados, principais resultados e conclusões.

<p align="center">
  <a href="https://www.youtube.com/watch?v=j6Jf3tsRY2E" target="_blank">
    <img src="https://img.youtube.com/vi/j6Jf3tsRY2E/maxresdefault.jpg" alt="Vídeo de apresentação do projeto" width="800">
  </a>
</p>

<p align="center">
  ▶️ <a href="https://www.youtube.com/watch?v=j6Jf3tsRY2E">Assistir no YouTube</a>
</p>

---

## 📂 Dataset

Foi construído um dataset próprio contendo **80 imagens**, distribuídas igualmente entre as classes gato e tênis.

A divisão utilizada foi:

| Conjunto | Gato | Tênis | Total |
|---|---:|---:|---:|
| Treinamento | 32 | 32 | 64 |
| Validação | 4 | 4 | 8 |
| Teste | 4 | 4 | 8 |
| **Total** | **40** | **40** | **80** |

As imagens utilizadas nos conjuntos de treinamento e validação foram anotadas por meio de **bounding boxes**, seguindo o formato esperado pela YOLO.

As classes foram definidas como:

- `0`: gato
- `1`: tenis

### Organização e validação do dataset

A estrutura do dataset foi organizada em diretórios separados para treinamento, validação e teste:

<p align="center">
  <img src="imagens/estrutura_dataset.jpg" width="800">
</p>

Antes do treinamento, foi realizada uma conferência da quantidade de imagens e arquivos de anotação presentes em cada conjunto:

<p align="center">
  <img src="imagens/validacao_dataset.jpg" width="800">
</p>

A estrutura utilizada durante os experimentos foi:

```text
dataset/
│
├── train/
│   ├── images/
│   └── labels/
│
├── val/
│   ├── images/
│   └── labels/
│
└── test/
    ├── images/
    └── labels/
```

---

## 📦 Carregamento do dataset no Google Colab

Inicialmente, o projeto previa o acesso ao dataset por meio da conexão entre o **Google Colab e o Google Drive**. Entretanto, durante o desenvolvimento foram encontrados problemas de autenticação que impediram a montagem do Drive no ambiente do Colab.

Como alternativa, o dataset foi organizado e compactado no arquivo:

`dataset.zip`

O arquivo é carregado diretamente no ambiente do Google Colab e posteriormente descompactado no diretório `/content`, permitindo que o notebook acesse normalmente as imagens e os arquivos de anotação utilizados nas etapas de treinamento, validação e teste.

O arquivo `dataset.zip` está disponibilizado neste repositório para permitir a reprodução do projeto.

Após realizar o upload do arquivo para o Google Colab, o dataset é descompactado por meio do comando:

```python
!unzip -q /content/dataset.zip -d /content/
```

Após a extração, a estrutura esperada é:

```text
/content/dataset/
│
├── train/
│   ├── images/
│   └── labels/
│
├── val/
│   ├── images/
│   └── labels/
│
└── test/
    ├── images/
    └── labels/
```

> **Importante:** para reproduzir o projeto, o arquivo `dataset.zip` deve ser carregado no ambiente do Google Colab antes da execução das células responsáveis pela preparação e treinamento do modelo.

Essa abordagem foi adotada como alternativa ao acesso direto pelo Google Drive e não altera as etapas do pipeline de visão computacional, que continuam contemplando **treinamento, validação e teste**.

---

## 🏷️ Anotação das imagens

As imagens destinadas ao treinamento e à validação foram anotadas utilizando o **Make Sense AI**.

Foram criadas bounding boxes para indicar a localização dos objetos pertencentes às classes gato e tênis.

As anotações foram exportadas no formato compatível com a YOLO, permitindo que cada objeto presente nas imagens fosse associado à sua respectiva classe e localização.

Os arquivos de anotação `.txt` foram posteriormente organizados juntamente com as respectivas imagens nas pastas `labels` do dataset.

As imagens do conjunto de teste foram mantidas separadas para a realização posterior das inferências e da avaliação qualitativa do modelo.

---

## 🧠 Modelo utilizado

Foi utilizada a arquitetura **YOLOv5s**, empregando pesos pré-treinados e a técnica de **Transfer Learning**.

Essa abordagem permite utilizar características visuais previamente aprendidas pelo modelo e adaptar seus parâmetros para as classes específicas utilizadas neste projeto.

Os principais parâmetros utilizados durante os experimentos foram:

| Parâmetro | Configuração |
|---|---|
| Modelo | YOLOv5s |
| Tamanho da imagem | 640 px |
| Batch size | 16 |
| Pesos iniciais | `yolov5s.pt` |
| Número de classes | 2 |
| Classes | gato e tênis |

O treinamento foi realizado utilizando GPU no ambiente **Google Colab**.

---

## 🧪 Experimentos realizados

Foram realizados três experimentos para analisar a influência da quantidade de épocas e da utilização do Early Stopping sobre o desempenho do detector.

Os principais parâmetros foram mantidos equivalentes entre os experimentos, permitindo uma comparação mais controlada entre as diferentes configurações.

### Experimento 1 — 30 épocas

O primeiro modelo foi treinado durante **30 épocas**, utilizando pesos pré-treinados da YOLOv5s.

Esse experimento foi utilizado como referência inicial para avaliar o comportamento do detector e permitir posteriormente a comparação com treinamentos mais longos.

### Experimento 2 — 60 épocas

No segundo experimento, o número de épocas foi aumentado para **60**, mantendo os demais parâmetros equivalentes ao primeiro treinamento.

O objetivo foi analisar se o aumento da quantidade de épocas proporcionaria melhoria no desempenho do modelo.

### Experimento 3 — Early Stopping

No terceiro experimento foi utilizada a técnica de **Early Stopping**.

O treinamento foi configurado com:

- limite máximo de **90 épocas**;
- `patience=10`;
- mesmo dataset;
- mesma arquitetura YOLOv5s;
- `img=640`;
- `batch=16`.

O mecanismo de Early Stopping interrompeu automaticamente o treinamento após **50 épocas**, sendo o melhor resultado registrado na **época 39**.

<p align="center">
  <img src="imagens/resultado_early_stopping.jpg" width="900">
</p>

O resultado demonstra a atuação do Early Stopping, interrompendo o processo quando não são observadas novas melhorias durante o período de paciência estabelecido.

---

## 📊 Resultados

Para avaliar os modelos foram utilizadas métricas adequadas a problemas de detecção de objetos, incluindo:

- **Precision:** proporção das detecções realizadas pelo modelo que correspondem corretamente aos objetos esperados;
- **Recall:** capacidade do modelo de encontrar os objetos presentes nas imagens;
- **mAP@0.5:** desempenho médio das detecções considerando IoU de 0,5;
- **mAP@0.5:0.95:** avaliação mais rigorosa considerando diferentes limiares de IoU entre 0,5 e 0,95.

Os resultados obtidos no conjunto de validação foram:

| Experimento | Épocas executadas | Precision | Recall | mAP@0.5 | mAP@0.5:0.95 | Tempo (h) |
|---|---:|---:|---:|---:|---:|---:|
| 30 épocas | 30 | 0,632 | 0,847 | 0,837 | 0,502 | 0,518 |
| 60 épocas | 60 | 0,967 | 0,811 | 0,947 | 0,737 | 1,038 |
| Early Stopping | 50 | 0,870 | 0,884 | 0,928 | 0,557 | 0,931 |

### Comparação dos experimentos

A comparação demonstra que o treinamento com **60 épocas** apresentou os maiores valores de Precision, mAP@0.5 e mAP@0.5:0.95.

Por outro lado, o experimento utilizando **Early Stopping** apresentou o maior Recall.

Os resultados demonstram que o aumento do número de épocas não produz necessariamente melhoria simultânea em todas as métricas, tornando importante analisar diferentes indicadores durante a avaliação de um modelo de detecção de objetos.

<p align="center">
  <img src="imagens/comparacao_experimentos.jpg" width="850">
</p>

As curvas de aprendizado e as análises detalhadas de cada treinamento estão disponíveis no notebook do projeto.

---

## 🔎 Teste do modelo

Após o treinamento e a comparação dos experimentos, o modelo preservado do experimento com **Early Stopping** foi utilizado para realizar inferências sobre as **8 imagens reservadas para teste**.

Essas imagens foram mantidas separadas das etapas de treinamento e validação.

Como as imagens de teste não foram utilizadas com anotações de referência para o cálculo das métricas, a avaliação nesta etapa foi realizada de maneira **qualitativa**, observando as classes previstas e as bounding boxes produzidas pelo detector.

### Exemplos de detecção

Nas imagens contendo objetos mais isolados, o modelo apresentou bounding boxes mais coerentes com a localização dos objetos.

#### Classe gato

<p align="center">
  <img src="imagens/teste_gato.jpg" width="350">
</p>

#### Classe tênis

<p align="center">
  <img src="imagens/teste_tenis.jpg" width="350">
</p>

Os exemplos demonstram que o modelo desenvolveu capacidade de reconhecer as duas classes estudadas em imagens que não participaram diretamente do processo de treinamento.

---

## 🔍 Situações mais desafiadoras

Também foram analisadas imagens contendo múltiplas instâncias da mesma classe.

### Múltiplos gatos

<p align="center">
  <img src="imagens/teste_gatos_multiplos.jpg" width="500">
</p>

### Múltiplos tênis

<p align="center">
  <img src="imagens/teste_tenis_multiplos.jpg" width="400">
</p>

Nessas situações, foram observadas limitações na individualização dos objetos. Algumas bounding boxes apresentaram sobreposição ou abrangeram mais de uma instância.

Esses resultados indicam que, embora o modelo tenha desenvolvido capacidade de reconhecer as classes gato e tênis, sua capacidade de localizar individualmente múltiplos objetos ainda pode ser aprimorada.

---

## ⚠️ Limitações

Uma das principais limitações do projeto está relacionada ao tamanho reduzido do conjunto de dados.

Embora as **80 imagens** sejam suficientes para a realização dos experimentos propostos, um dataset com maior quantidade e diversidade de exemplos poderia contribuir para aumentar a capacidade de generalização do detector.

Também deve ser considerado o tamanho reduzido do conjunto de validação, composto por apenas **8 imagens e 14 instâncias**. Dessa forma, pequenas alterações nas detecções podem provocar variações relevantes nas métricas.

Outras limitações observadas incluem situações com múltiplos objetos, objetos próximos e determinados enquadramentos nos quais a localização individual das instâncias se mostrou mais difícil.

Como possibilidades de continuidade, poderiam ser avaliadas:

- ampliação do dataset;
- maior diversidade de cenários e condições de iluminação;
- maior quantidade de imagens contendo múltiplas instâncias;
- técnicas de Data Augmentation;
- ajustes adicionais de hiperparâmetros;
- comparação com outras arquiteturas de visão computacional.

---

## 🛠️ Tecnologias utilizadas

As principais tecnologias e ferramentas utilizadas no desenvolvimento foram:

- Python
- PyTorch
- YOLOv5
- Google Colab
- OpenCV
- Matplotlib
- Pandas
- Make Sense AI
- Git
- GitHub

---

## 📓 Notebook

O notebook contém o desenvolvimento completo do projeto, incluindo:

- preparação do ambiente;
- carregamento e organização do dataset;
- conferência das imagens e anotações;
- configuração da YOLOv5;
- treinamento com 30 épocas;
- treinamento com 60 épocas;
- treinamento utilizando Early Stopping;
- validação e análise das métricas;
- análise das curvas de aprendizado;
- comparação entre os experimentos;
- aplicação do modelo sobre o conjunto de teste;
- análise das detecções;
- limitações e conclusão.

O arquivo principal do projeto é:

`RenataDeAlmeidaMarinho_rm569346_PedroHenriqueDeLacerda_rm573114_GiselliMayumiTakahashiYokoyama_rm572690_JoaoOtavioMoraes_rm573227_DavidRibeiroPradoDeLacerda_rm570350_pbl_fase06.ipynb`

---

## 📁 Estrutura do repositório

A estrutura principal do repositório está organizada da seguinte forma:

```text
projeto-fase6/
│
├── README.md
│
├── dataset.zip
│
├── RenataDeAlmeidaMarinho_..._pbl_fase06.ipynb
│
└── imagens/
    ├── estrutura_dataset.jpg
    ├── validacao_dataset.jpg
    ├── resultado_early_stopping.jpg
    ├── comparacao_experimentos.jpg
    ├── teste_gato.jpg
    ├── teste_gatos_multiplos.jpg
    ├── teste_tenis.jpg
    └── teste_tenis_multiplos.jpg
```

O arquivo `dataset.zip` contém as imagens e anotações necessárias para reproduzir o pipeline utilizado no notebook.

---

## ▶️ Como executar

O projeto foi desenvolvido utilizando o **Google Colab**.

Para reproduzir o pipeline:

1. Faça o download do arquivo `dataset.zip` disponibilizado neste repositório.

2. Abra o notebook do projeto no Google Colab.

3. Ative uma GPU acessando:

   `Ambiente de execução > Alterar tipo de ambiente de execução > GPU`

4. Faça o upload do arquivo `dataset.zip` para o ambiente do Google Colab.

5. Execute a célula responsável pela descompactação:

```python
!unzip -q /content/dataset.zip -d /content/
```

6. Após a extração, verifique se o dataset está disponível em:

```text
/content/dataset/
```

7. Execute as células responsáveis pela conferência da estrutura e da quantidade de imagens e anotações.

8. Execute as células de instalação e configuração da YOLOv5.

9. Execute as etapas de treinamento e validação apresentadas no notebook.

10. Após o treinamento, execute as células de inferência para realizar os testes nas imagens reservadas para essa finalidade.

> **Importante:** o diretório `/content` do Google Colab possui armazenamento temporário. Caso a sessão seja encerrada ou reiniciada, poderá ser necessário realizar novamente o upload do `dataset.zip` e sua descompactação.

> **Observação:** o tempo de treinamento pode variar de acordo com a GPU disponibilizada pelo Google Colab.

---

## 🎓 Considerações finais

O desenvolvimento deste projeto possibilitou aplicar conceitos fundamentais de **Visão Computacional e Deep Learning**, envolvendo preparação e anotação de dados, Transfer Learning, treinamento de modelos de detecção de objetos e avaliação por meio de métricas como Precision, Recall e mAP.

A realização dos diferentes experimentos permitiu observar como alterações na quantidade de épocas e a utilização do Early Stopping influenciam o comportamento do detector.

Os testes realizados em imagens separadas das etapas de treinamento e validação também permitiram identificar tanto a capacidade do modelo de reconhecer as classes estudadas quanto suas limitações em cenários contendo múltiplas instâncias.

A utilização do `dataset.zip` como forma de disponibilização dos dados permitiu contornar a dificuldade encontrada na autenticação entre o Google Colab e o Google Drive, mantendo o pipeline de treinamento, validação e teste reproduzível.

Dessa forma, o projeto permitiu compreender não apenas o processo de treinamento de uma YOLOv5 customizada, mas também a importância da organização dos dados, da análise conjunta das métricas, da avaliação crítica dos resultados e da adoção de soluções alternativas diante de limitações encontradas durante o desenvolvimento.