#include "DHT.h"

// Definição dos pinos conforme diagram.json
#define PIN_LDR 15
#define PIN_DHT 32
#define PIN_RELAY 14
#define PIN_BTN_N 16 // Botão 3 no diagrama
#define PIN_BTN_P 22 // Botão 2 no diagrama
#define PIN_BTN_K 25 // Botão 1 no diagrama

#define DHTTYPE DHT22
DHT dht(PIN_DHT, DHTTYPE);

// Nível de chuva prevista (em mm), atualizado via Serial pelo Python
float chuvaPrevista = 0.0;

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(50); // Reduz latencia na leitura do Serial
  dht.begin();

  pinMode(PIN_RELAY, OUTPUT);

  // Configura os botões com resistor interno
  pinMode(PIN_BTN_N, INPUT_PULLUP);
  pinMode(PIN_BTN_P, INPUT_PULLUP);
  pinMode(PIN_BTN_K, INPUT_PULLUP);

  digitalWrite(PIN_RELAY, LOW);
  Serial.println("FARMTECH - IRRIGACAO INTELIGENTE - CULTURA: MILHO");
  Serial.println("Digite o nivel de chuva prevista em mm e pressione Enter (ex: 8.5)");
}

void loop() {
  // Lê chuva prevista enviada pelo Python via Serial Monitor
  if (Serial.available() > 0) {
    String entrada = Serial.readStringUntil('\n');
    entrada.trim();
    if (entrada.length() > 0) {
      chuvaPrevista = entrada.toFloat();
      Serial.print(">>> Chuva prevista atualizada: ");
      Serial.print(chuvaPrevista);
      Serial.println(" mm");
    }
  }

  // 1. Leitura da Umidade (Solo)
  float umidade = dht.readHumidity();

  // Tratamento de erro: se o DHT22 falhar, aborta este ciclo
  if (isnan(umidade)) {
    Serial.println("Erro na leitura do DHT22");
    delay(2000);
    return;
  }

  // 2. Lógica do pH (LDR + Influência NPK)
  int ldrRaw = analogRead(PIN_LDR);
  // Converte a leitura analógica (0-4095) para escala de pH (0.0-14.0)
  float phBase = (ldrRaw / 4095.0) * 14.0;
  float phFinal = phBase;

  // Verifica os botões (LOW significa pressionado devido ao PULLUP)
  bool nPressionado = (digitalRead(PIN_BTN_N) == LOW);
  bool pPressionado = (digitalRead(PIN_BTN_P) == LOW);
  bool kPressionado = (digitalRead(PIN_BTN_K) == LOW);

  // Altera o pH conforme os nutrientes presentes (simplificacao didatica)
  if (nPressionado) phFinal -= 2.0; // N deixa mais ácido
  if (pPressionado) phFinal += 1.5; // P deixa mais básico
  if (kPressionado) phFinal += 0.5; // K deixa levemente básico

  // Restringe o valor final para a escala real de pH
  if (phFinal < 0) phFinal = 0;
  if (phFinal > 14) phFinal = 14;

  // 3. Decisão de irrigação - faixas para CULTURA DE MILHO
  // Faixa de pH 5.5-7.0 conforme recomendacao da Embrapa Milho e Sorgo
  // Umidade <50% indica solo seco, necessitando irrigacao
  // Irrigacao so ocorre com nutrientes presentes para evitar lixiviacao
  bool soloSeco = umidade < 50.0;
  bool phOk = (phFinal >= 5.5 && phFinal <= 7.0);
  bool temNutriente = nPressionado || pPressionado || kPressionado;
  bool choveuOuVaiChover = chuvaPrevista >= 5.0;

  bool ligarBomba;
  String motivo;

  // Chuva tem prioridade sobre todas as outras condições
  if (choveuOuVaiChover) {
    ligarBomba = false;
    motivo = "chuva prevista";
  } else if (!soloSeco) {
    ligarBomba = false;
    motivo = "umidade ok";
  } else if (!phOk) {
    ligarBomba = false;
    motivo = "pH fora da faixa";
  } else if (!temNutriente) {
    ligarBomba = false;
    motivo = "sem nutrientes";
  } else {
    ligarBomba = true;
    motivo = "irrigando";
  }

  digitalWrite(PIN_RELAY, ligarBomba ? HIGH : LOW);

  // 4. Exibição dos Resultados
  Serial.print("Umidade: "); Serial.print(umidade); Serial.print("% | ");
  Serial.print("pH Final: "); Serial.print(phFinal);
  Serial.print(" | [");
  Serial.print(nPressionado ? "N" : "-");
  Serial.print(pPressionado ? "P" : "-");
  Serial.print(kPressionado ? "K" : "-");
  Serial.print("] | Chuva: "); Serial.print(chuvaPrevista); Serial.print("mm");
  Serial.print(" | Bomba: ");
  Serial.print(ligarBomba ? "LIGADA" : "DESLIGADA");
  Serial.print(" | Motivo: "); Serial.println(motivo);

  delay(2000);
}