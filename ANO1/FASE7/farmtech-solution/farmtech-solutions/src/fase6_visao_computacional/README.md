# Fase 6 — Visão computacional com YOLO

Detecção de quatro pragas de soja e milho, com inferência local e integração à aba **Detecção de Pragas** da dashboard Streamlit. O enunciado exige visão computacional com YOLO integrada à dashboard e não define meta mínima de métrica.

## Dataset e classes

Usamos somente o **AgroInsect v2**, Mendeley Data, [DOI 10.17632/4jyp4m9gxj.2](https://doi.org/10.17632/4jyp4m9gxj.2), licença [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). São 1.510 imagens e 1.510 arquivos de rótulos YOLO.

O arquivo distribuído não inclui nomes de classes. O mapeamento de `pragas.py` foi conferido visualmente:

| ID | Espécie | Nome usado no serviço |
|---|---|---|
| 0 | Diabrotica speciosa | Vaquinha |
| 1 | Dalbulus maidis | Cigarrinha-do-milho |
| 2 | Diceraeus spp. | Percevejo-barriga-verde |
| 3 | Spodoptera frugiperda | Mariposa da lagarta-do-cartucho |

**Ressalva da classe 3:** as imagens mostram principalmente a mariposa adulta. Detectar essa classe não confirma a presença de lagartas no cartucho. Essa ressalva também aparece na dashboard e na ação corretiva exportada em CSV/JSON para os alertas.

## Ambiente

Execute os comandos PowerShell na raiz do repositório. Prefira Python 3.11 de 64 bits e GPU NVIDIA. Verifique `nvidia-smi`, espaço em disco, RAM e memória virtual antes do treino. A disponibilidade de CUDA, sozinha, não garante memória suficiente para treinar.

A GPU só é necessária para treinar em tempo razoável. Sem ela, o script usa a CPU automaticamente, mas o treino pode levar horas. A detecção e a dashboard funcionam sem GPU e sem treinar, com o modelo incluído no repositório. Nesse caso, basta `pip install -r requirements.txt`.

```powershell
python --version
nvidia-smi
python -m venv .venv
# Exemplo usado na RTX 5060 Ti, driver 610.88:
.\.venv\Scripts\python.exe -m pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.version.cuda); print(torch.cuda.is_available())"
```

Escolha o pacote CUDA conforme a GPU e o driver, seguindo as [instruções oficiais do PyTorch](https://pytorch.org/get-started/previous-versions/).

## Baixar e extrair

Baixe `AgroInsect.rar` na raiz do projeto e confira o SHA-256 **antes** de extrair:

```powershell
curl.exe --fail --location --output AgroInsect.rar "https://data.mendeley.com/public-files/datasets/4jyp4m9gxj/files/efce9b61-ba01-42a1-a6be-0be1bbadddd8/file_downloaded"
$hash = (Get-FileHash -LiteralPath AgroInsect.rar -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hash -ne 'd2c1daa5c54266858504bdb60224bda8768c2909b0dc7c292d47dba88beb200d') { throw 'SHA-256 divergente' }
New-Item -ItemType Directory -Force src/fase6_visao_computacional/dataset/raw | Out-Null
& C:\Windows\System32\tar.exe -xf AgroInsect.rar -C src/fase6_visao_computacional/dataset/raw
if ($LASTEXITCODE -ne 0) { throw 'Falha ao extrair AgroInsect' }
(Get-ChildItem src/fase6_visao_computacional/dataset/raw/image -File).Count
(Get-ChildItem src/fase6_visao_computacional/dataset/raw/label -File).Count
# Apague apenas após confirmar 1.510 arquivos em cada pasta:
Remove-Item -LiteralPath AgroInsect.rar
```

No Windows, use o `tar.exe` acima; o tar do Git Bash não abre esse RAR. A estrutura final precisa ser `dataset/raw/image/` e `dataset/raw/label/`, sem uma pasta intermediária.

## Preparar

```powershell
.\.venv\Scripts\python.exe src/fase6_visao_computacional/preparar_dataset.py --seed 42
```

O script agrupa imagens duplicadas ou quase iguais por hash perceptual e mantém cada grupo no mesmo conjunto. Gera `dataset/yolo/data.yaml` com o caminho absoluto da máquina em uso e `dataset/yolo/divisao.csv`. Reexecutá-lo substitui a pasta `dataset/yolo`.

Divisão verificada localmente em 6 de novembro de 2026:

| Classe | Treino | Validação | Teste |
|---|---:|---:|---:|
| Diabrotica speciosa | 442 | 95 | 94 |
| Dalbulus maidis | 152 | 33 | 32 |
| Diceraeus spp. | 196 | 42 | 41 |
| Spodoptera frugiperda | 269 | 57 | 57 |
| **Total** | **1.059** | **227** | **224** |

Foram identificadas 54 imagens em grupos de duplicatas. A preparação leu as imagens com sucesso; o scanner do Ultralytics reportou zero imagens corrompidas em treino e validação.

## Treinar e avaliar

```powershell
.\.venv\Scripts\python.exe src/fase6_visao_computacional/treinar.py --batch 8 --workers 0 --imgsz 640 --epochs 90 --patience 10 --seed 42
```

O modelo solicitado é `yolov5s.pt`, carregado pelo Ultralytics como `yolov5su.pt`. Cada execução inicia um treino novo a partir desses pesos pré-treinados. O batch padrão é 8; use 16 somente quando houver pelo menos 6 GB livres na GPU e memória de sistema suficiente. O padrão de `--workers` é 0, o valor do treino validado; valores maiores podem acelerar, mas usam mais memória.

As saídas do treino ficam em `runs/agroinsect/`. Ao terminar com sucesso, o script copia o melhor checkpoint para `modelos/best.pt`, avalia as **224 imagens de teste** e grava `modelos/metricas_teste.json`, com precisão, recall, mAP@0.5 e mAP@0.5:0.95, gerais e por classe. O conjunto de teste não é usado para selecionar o melhor checkpoint. `patience=10` permite encerrar antes das 90 épocas.

## Resultado real do treino e do teste

Treino concluído em 6 de novembro de 2026, com código de saída 0. Foram **80 épocas**, encerradas por early stopping (`patience=10`); o melhor checkpoint veio da **época 70**. O tempo registrado em `results.csv` foi **2.038,79 segundos (33 min 59 s)**, média de **25,5 s/época** (mediana 25,7 s).

Configuração efetivamente executada: `yolov5s.pt` → `yolov5su.pt`, imagens 640, limite de 90 épocas, seed 42, **batch 8**, **workers 0**, `resume=False`. O batch 16 falhou em uma tentativa anterior; mantivemos 8 para esta execução estável.

Ambiente: Windows 11, Python 3.11.9, RTX 5060 Ti de 16 GB, driver 610.88, PyTorch 2.11.0+cu128, torchvision 0.26.0+cu128 e Ultralytics 8.4.203. `pip check` passou; CUDA e uma operação matricial na GPU foram testadas.

O script confirmou `modelos/best.pt` (18.501.826 bytes) e `modelos/metricas_teste.json`. SHA-256 do melhor peso: `0f354544460cbf967b7c2cc9cceb67e3da5d1dc03d70e955a7fa15b5ee950e39`.

Avaliação feita no conjunto de **224 imagens de teste e 245 instâncias contabilizadas pelo avaliador**, sem usar esse conjunto para selecionar o checkpoint. Valores abaixo em escala de 0 a 1, copiados do JSON gerado pelo script:

| Classe | Precisão | Recall | mAP@0.5 | mAP@0.5:0.95 |
|---|---:|---:|---:|---:|
| **Geral** | 0.8921 | 0.8860 | 0.9273 | 0.5564 |
| Diabrotica speciosa | 0.9432 | 0.9362 | 0.9792 | 0.5179 |
| Dalbulus maidis | 0.7994 | 0.8636 | 0.8581 | 0.4263 |
| Diceraeus spp. | 0.8900 | 0.8182 | 0.9023 | 0.5563 |
| Spodoptera frugiperda | 0.9358 | 0.9259 | 0.9695 | 0.7252 |

São métricas do conjunto reservado deste dataset, não uma garantia de desempenho em novas lavouras. A precisão e o recall reportados pelo avaliador não devem ser confundidos com o teste funcional de inferência a confiança fixa de 0,25.

### Testes funcionais

`inferir.py` foi executado com `--conf 0.25` nas **224 imagens de teste**, com código de saída 0. Foram verificadas 224 imagens anotadas legíveis, CSV e JSON coerentes com **280 detecções em 220 imagens**. As quatro classes apareceram nas saídas: 101 detecções de classe 0, 60 de classe 1, 51 de classe 2 e 68 de classe 3. Essas contagens não substituem as métricas de detecção acima. A ressalva sobre mariposas adultas foi conferida nos alertas exportados da classe 3.

O fluxo real de **upload → Detectar pragas → imagem anotada → tabela → ação corretiva** passou na dashboard local com uma imagem de teste de cada classe e confiança 0,25:

| Classe | Imagem de teste | Detecções exibidas |
|---|---|---:|
| Diabrotica speciosa | `51b5c066-imag11.jpg` | 1 |
| Dalbulus maidis | `b51d8569-imag62.jpg` | 3 |
| Diceraeus spp. | `c9e4bfc0-imag107.jpg` | 1 |
| Spodoptera frugiperda | `a489167b-imag91.jpg` | 1 |

A ressalva da mariposa adulta apareceu no aviso da aba e na ação corretiva da classe 3.

### Problemas de memória no treino

As primeiras tentativas falharam por falta de memória: `WinError 1455` ao carregar uma DLL do CUDA em um worker, falta de memória CUDA com batch 16 e falta de memória no OpenCV. A execução bem-sucedida usou batch 8 e workers 0 desde o início.

## Inferir e testar a dashboard

`modelos/best.pt` já vem no repositório, então não é preciso treinar para testar. A pasta `amostras/` traz uma imagem do conjunto de teste de cada praga, renomeada a partir do AgroInsect:

| Arquivo em `amostras/` | Imagem original |
|---|---|
| `vaquinha.jpg` | `51b5c066-imag11.jpg` |
| `cigarrinha_do_milho.jpg` | `b51d8569-imag62.jpg` |
| `percevejo_barriga_verde.jpg` | `c9e4bfc0-imag107.jpg` |
| `mariposa_da_lagarta_do_cartucho.jpg` | `a489167b-imag91.jpg` |

```powershell
# Use uma imagem ou uma pasta:
.\.venv\Scripts\python.exe src/fase6_visao_computacional/inferir.py --fonte src/fase6_visao_computacional/amostras --conf 0.25
.\.venv\Scripts\python.exe -m streamlit run src/dashboard/streamlit_app.py --server.port 8502
```

A inferência salva `resultados/deteccoes.csv`, `resultados/deteccoes.json` e imagens anotadas em `resultados/imagens/`. As saídas são substituídas a cada execução. Cada detecção inclui classe, confiança, caixa e ação corretiva.

Na aba **Detecção de Pragas**, envie uma imagem ou escolha um exemplo da lista, mantenha confiança 0,25 e clique em **Detectar pragas**. Confira imagem anotada, tabela, ações corretivas e os arquivos gerados. Repita com imagens das quatro classes. Se a imagem estiver corrompida ou o subprocesso falhar, a dashboard exibe o diagnóstico completo e grava `resultados/erro_deteccao.log` com comando, código de saída, stdout e stderr.

## Limitações

- O modelo cobre somente quatro classes; não avalia doenças, crescimento irregular ou outras pragas.
- O mapeamento de IDs foi conferido visualmente; não veio como arquivo de nomes no dataset.
- A classe 3 representa principalmente o adulto, e não valida detecção de lagartas.
- O dataset é pequeno e desbalanceado. Agrupar duplicatas reduz vazamento, mas não substitui validação externa em novas lavouras, condições de luz e equipamentos.
- A confiança de 0,25 é um limiar de inferência, não uma garantia de acerto. Ausência de detecção não prova ausência de pragas.
- As ações são orientações de vistoria e encaminhamento ao agrônomo; uma detecção isolada não determina aplicação de defensivos.
- Nenhum limiar mínimo de métrica foi exigido pelo enunciado. A conclusão do serviço corresponde ao treino, à avaliação e aos fluxos funcionais registrados acima; os alertas na AWS são uma entrega separada.

`modelos/best.pt` (aproximadamente 18,5 MB) e `modelos/metricas_teste.json` são versionados diretamente no Git para que um clone já possa executar a inferência e mostrar as métricas na dashboard, sem novo treino. O arquivo de pesos é binário, sem Git LFS. Dataset, `runs/`, `resultados/`, logs, ambiente virtual e os demais pesos `.pt` continuam ignorados. O `last.pt` é um artefato de continuação do treino e não é necessário para inferir. No encerramento normal, o Ultralytics pode remover dele o estado do otimizador; não se deve presumir que todo `last.pt` permita retomar exatamente o treino.

## Referência

Guilherme de Almeida; Leonardo Nazario; Marconi Teixeira; Jéssica Stirle; Heyde Franca; Mario Oliveira; Ruy Oliveira; Sergio Novak; Adriano Bailão; Pablo Gontijo. **AGROINSECT: A dataset for identifying agricultural insects and pests of interest.** Mendeley Data, versão 2, 2026. DOI: [10.17632/4jyp4m9gxj.2](https://doi.org/10.17632/4jyp4m9gxj.2). Licença CC BY 4.0. O projeto reorganiza os arquivos em treino, validação e teste e associa nomes aos IDs após conferência visual.
