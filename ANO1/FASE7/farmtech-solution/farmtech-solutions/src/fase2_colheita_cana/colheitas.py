import os

faixas_velocidade = ("lenta", "moderada", "rapida")

tabela_perdas = [
    {"velocidade": 3.0, "perda": 2.25, "faixa_velocidade": "lenta"},
    {"velocidade": 4.0, "perda": 2.40, "faixa_velocidade": "lenta"},
    {"velocidade": 5.0, "perda": 2.22, "faixa_velocidade": "lenta"},
    {"velocidade": 6.0, "perda": 4.16, "faixa_velocidade": "moderada"},
    {"velocidade": 7.0, "perda": 4.84, "faixa_velocidade": "rapida"},
    {"velocidade": 8.0, "perda": 4.59, "faixa_velocidade": "rapida"},
]

def pedir_numero(mensagem):
    while True:
        try:
            valor = float(input(mensagem))
            if valor > 0:
                return valor
            os.system('cls' if os.name == 'nt' else 'clear')
            print("Valor deve ser positivo. Tente novamente.")
        except ValueError:
            os.system('cls' if os.name == 'nt' else 'clear')
            print("Entrada inválida. Digite um número.")


def pedir_velocidade():
    while True:
        try:
            velocidade = float(input("Digite a velocidade da colhedora (3.0 a 8.0 km/h): "))
            if 3.0 <= velocidade <= 8.0:
                velocidades_validas = [linha["velocidade"] for linha in tabela_perdas]
                mais_proximo = min(velocidades_validas, key=lambda v: abs(v - velocidade))
                print(f"Velocidade aproximada para: {mais_proximo} km/h")
                return mais_proximo
            os.system('cls' if os.name == 'nt' else 'clear')
            print("Velocidade inválida! Digite um valor entre 3.0 e 8.0 km/h.")
        except ValueError:
            os.system('cls' if os.name == 'nt' else 'clear')
            print("Entrada inválida. Digite um número.")


def pedir_clima():
    while True:
        clima = input("Digite o clima durante a colheita (seco/chuvoso): ").strip().lower()
        if clima in ("seco", "chuvoso"):
            return clima
        os.system('cls' if os.name == 'nt' else 'clear')
        print("Clima inválido. Tente novamente.")


def calcular_perda(area_ha, producao_ton, velocidade, clima):
    for linha in tabela_perdas:
        if linha["velocidade"] == velocidade:
            percentual_perda = linha["perda"]
            faixa_velocidade = linha["faixa_velocidade"]
            break

    perda = producao_ton * (percentual_perda / 100)

    return {
        "area_ha": area_ha,
        "producao_bruta": producao_ton,
        "velocidade_kmh": velocidade,
        "faixa_velocidade": faixa_velocidade,
        "clima": clima,
        "percentual_perda": round(percentual_perda, 2),
        "perda_ton": round(perda, 2),
        "producao_liquida": round(producao_ton - perda, 2)
    }
    

def gerar_recomendacao(faixa_velocidade, velocidades_validas, clima, percentual):
    print("\nRecomendações (critérios SOCICANA):")
    
    if faixa_velocidade == velocidades_validas[2]:  # rápida
        print("- 🚨 Reduza a velocidade para 5 km/h ou menos.")
    elif faixa_velocidade == velocidades_validas[1]:  # moderada
        print("- ⚠️  Velocidade moderada, pode ser otimizada.")
    else: # lenta
        print("- ✅ Velocidade adequada.")

    if clima == "chuvoso":
        print("- ⚠️  Transporte rápido da cana para evitar deterioração.")

    if percentual <= 3:
        print("- ✅ Nível BAIXO de perda (SOCICANA).")
    elif percentual <= 4.5:
        print("- ⚠️  Nível MÉDIO de perda (SOCICANA).")
    else:
        print("- 🚨 Nível ALTO de perda (SOCICANA).")


def exibir_resultados(resultados):
    for resultado in resultados:
        print(f"Área: {resultado['area_ha']} ha")
        print(f"Produção Bruta: {resultado['producao_bruta']} ton")
        print(f"Produção Líquida: {resultado['producao_liquida']} ton")
        print(f"Perda: {resultado['perda_ton']} ton")
        print(f"Percentual de Perda: {resultado['percentual_perda']}%")
        print(f"Faixa de Velocidade: {resultado['faixa_velocidade']}")
        print(f"Velocidade: {resultado['velocidade_kmh']} km/h")
        print(f"Clima: {resultado['clima']}")

        percentual = resultado['percentual_perda']
        
        if percentual <= 3:
            nivel = "BAIXO"
        elif percentual <= 4.5:
            nivel = "MÉDIO"
        else:
            nivel = "ALTO"
        print(f"Nível de Perda (SOCICANA): {nivel}")
        print("-" * 30)

    media = sum(r["percentual_perda"] for r in resultados) / len(resultados)
    print(f"\n Média de perda no histórico: {round(media, 2)}%")