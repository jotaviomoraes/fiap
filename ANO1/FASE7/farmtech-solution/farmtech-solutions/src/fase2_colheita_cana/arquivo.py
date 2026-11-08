import json

arquivo_json = 'dados.json'
arquivo_txt = 'relatorio.txt'

def carregar_historico():
    try:
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except ValueError:
        # Encerra sem salvar, para não sobrescrever um arquivo que pode ser recuperado
        raise SystemExit(f"Arquivo {arquivo_json} inválido. Corrija-o antes de continuar.")

def salvar_historico(historico):   
    with open(arquivo_json, 'w', encoding='utf-8') as f:
        json.dump(historico, f, ensure_ascii=False, indent=4)

def salvar_relatorio(historico):
    with open(arquivo_txt, 'w', encoding='utf-8') as f:
        f.write("Relatório de perdas na colheita de cana\n")
        f.write("=" * 40 + "\n")
        for registro in historico:
            f.write(f"Área: {registro['area_ha']} ha\n")
            f.write(f"Produção Bruta: {registro['producao_bruta']} ton\n")
            f.write(f"Produção Líquida: {registro['producao_liquida']} ton\n")
            f.write(f"Perda: {registro['perda_ton']} ton\n")
            f.write(f"Percentual de Perda: {registro['percentual_perda']}%\n")
            f.write(f"Faixa de Velocidade: {registro['faixa_velocidade']}\n")
            f.write(f"Velocidade: {registro['velocidade_kmh']} km/h\n")
            f.write(f"Clima: {registro['clima']}\n")
            

            percentual = registro['percentual_perda']
            if percentual <= 3:
                nivel = "BAIXO"
            elif percentual <= 4.5:
                nivel = "MÉDIO"
            else:
                nivel = "ALTO"
            f.write(f"Nível de Perda (SOCICANA): {nivel}\n")
            f.write("-" * 40 + "\n")

        media = sum(r["percentual_perda"] for r in historico) / len(historico)
        f.write(f"\nMédia geral de perda: {round(media, 2)}%\n")
    
    print("Relatório exportado com sucesso!")