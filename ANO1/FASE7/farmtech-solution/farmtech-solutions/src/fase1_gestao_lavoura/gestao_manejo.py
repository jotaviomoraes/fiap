import csv # Importação da biblioteca para manipulação de arquivos CSV
import os

# Estrutura de dados para armazenar os registros

culturas = []
areas = []
insumos = []
qtd_ruas = []

def limpar_tela():
        os.system('cls' if os.name == 'nt' else 'clear') # Função para limpar a tela do terminal

def carregar_dados(): # Função para carregar os registros salvos, evitando perdê-los ao salvar novamente
        if not os.path.exists('dados_farmtech.csv'):
                return

        try:
                with open('dados_farmtech.csv', mode='r', newline='', encoding='utf-8') as arquivo:
                        for linha in csv.DictReader(arquivo):
                                culturas.append(linha['Cultura'])
                                areas.append(float(linha['Area_m2']))
                                insumos.append(linha['Insumo'])
                                qtd_ruas.append(int(linha['Qtd_Ruas']))
        except (KeyError, TypeError, ValueError):
                # Encerra sem salvar, para não sobrescrever um arquivo que pode ser recuperado
                raise SystemExit("Arquivo dados_farmtech.csv inválido. Corrija-o antes de abrir o programa.")

carregar_dados()

# Loop principal do programa

while True:
        limpar_tela()

        
        print("\n=== FarmTech Solutions - Sistema de Manejo ===")
        print("1. Entrada de dados (Novo registro)")
        print("2. Saída de dados (Listar registros)")
        print("3. Atualização de dados")
        print("4. Deleção de dados")
        print("5. Sair do programa (Salvar dados)")

        opcao = input("Selecione uma opção (1-5): ")

        if opcao == '1': # Opção para entrada de dados e cálculo do manejo
                cultura_opcao = input("Tipo de cultura (1 para Café, 2 para Soja): ")

                if cultura_opcao in ['1', '2']:
                        cultura = "Café" if cultura_opcao == '1' else "Soja"

                        print("\nOpções de Insumo:")
                        print("1. Fertilizante NPK (Nutrição)")
                        print("2. Calcário (Correção de solo)")
                        insumo_opcao = input("Escolha o insumo (1 ou 2): ")

                        if insumo_opcao == '1':
                                insumo = "Fertilizante NPK"
                                taxa_ha = 600 if cultura == "Café" else 300 # Se for Café, 600 kg/ha; se for Soja, 300 kg/ha
                        elif insumo_opcao == '2':
                                insumo = "Calcário"
                                taxa_ha = 2500 if cultura == "Café" else 2000 # Se for Café, 2500 kg/ha; se for Soja, 2000 kg/ha
                        else:
                                print("Opção de insumo inválida. Tente novamente.")
                                input("\nPressione Enter para voltar ao menu...")
                                continue
                        try:
                                base = float(input(f"Digite a base do terreno para {cultura} (em metros): "))
                                altura = float(input("Digite a altura do terreno (em metros): "))   
                                entrelinhas = float(input("Digite o espaçamento entre as linhas (em metros): "))

                        except ValueError:
                                print("Valor inválido. Digite apenas números.")
                                input("\nPressione Enter para voltar ao menu...")
                                continue
                                
                        if base <= 0 or altura <= 0 or entrelinhas <= 0:
                                print("Valor inválido. As medidas devem ser maiores que zero.")
                                input("\nPressione Enter para voltar ao menu...")
                                continue

                        area = base * altura
                        ruas = altura / entrelinhas
                        hectares = area / 10000
                        quantidade_total_kg = hectares * taxa_ha

                        print(f"\n--- Resumo do Manejo de {cultura} ---")
                        print(f"Área total: {area:.2f} m² ({hectares:.2f} hectares).")
                        print(f"A lavoura possui {int(ruas)} ruas.")
                        print(f"Insumo selecionado: {insumo}")
                        print(f"Taxa recomendada: {taxa_ha} kg por hectare.")
                        print(f"Total necessário: {quantidade_total_kg:.2f} kg de {insumo} para toda a área.")

                        culturas.append(cultura)
                        areas.append(area)
                        insumos.append(insumo)
                        qtd_ruas.append(int(ruas))
                        print("\nDados registrados com sucesso!")
                        input("\nPressione Enter para voltar ao menu...")
                
                else:
                        print("Opção de cultura inválida. Por favor, escolha 1 para Café ou 2 para Soja.")
                        input("\nPressione Enter para voltar ao menu...")
                        continue

                

        elif opcao == '2': # Opção para listar os registros existentes
                if not culturas:
                        print("Nenhum registro encontrado.")
                else:
                        print("\n=== Registros de Culturas ===")
                        for i in range(len(culturas)):
                                cult_atual = culturas[i]
                                ins_atual = insumos[i]
                                area_atual = areas[i]

                                if cult_atual == "Café":
                                        taxa = 600 if ins_atual == "Fertilizante NPK" else 2500 # Se for Café
                                
                                else:
                                        taxa = 300 if ins_atual == "Fertilizante NPK" else 2000 # Se for Soja

                                kg_total = (area_atual / 10000) * taxa

                                print(f"\nID [{i}] | Cultura: {cult_atual} | Insumo: {ins_atual} | Área: {area_atual:.2f} m² | Ruas: {qtd_ruas[i]}")
                                print(f"Recomendação: {ins_atual} - {taxa} kg/ha (Total necessário: {kg_total:.2f} kg)")

                input("\nPressione Enter para voltar ao menu...")
                                
                        
        elif opcao == '3': # Opção para atualizar um registro existente
                if not culturas:
                        print("Nenhum registro encontrado para atualizar.")
                        input("\nPressione Enter para voltar ao menu...")

                else:
                        while True:
                                try:
                                     id_atualizar = int(input("Digite o ID do registro que deseja atualizar: "))
                                     break
                                except ValueError:
                                     print("ID inválido. Por favor, digite um número inteiro.")

                        if 0 <= id_atualizar < len(culturas):
                                dado_atualizar = input("Digite o campo que deseja atualizar (cultura, insumo ou área): ").lower()

                                
                                if dado_atualizar == 'cultura':
                                        nova_cultura = input("Digite a nova cultura (1 para Café, 2 para Soja): ")
                                        if nova_cultura == '1':
                                                culturas[id_atualizar] = "Café"
                                        elif nova_cultura == '2':
                                                culturas[id_atualizar] = "Soja"
                                        else:
                                                print("Opção de cultura inválida. Atualização cancelada.")
                                                input("\nPressione Enter para voltar ao menu...")
                                                continue
                                
                                elif dado_atualizar == 'insumo':
                                        print("\nOpções de Insumo:")
                                        print("1. Fertilizante NPK (Nutrição)")
                                        print("2. Calcário (Correção de solo)")
                                        novo_insumo_opcao = input("Escolha o novo insumo (1 ou 2): ")

                                        if novo_insumo_opcao == '1':
                                                insumos[id_atualizar] = "Fertilizante NPK"
                                        elif novo_insumo_opcao == '2':
                                                insumos[id_atualizar] = "Calcário"
                                        else:
                                                print("Opção de insumo inválida. Atualização cancelada.")
                                                input("\nPressione Enter para voltar ao menu...")
                                                continue

                                elif dado_atualizar in ['área', 'area']:
                                        print("\nPara atualizar a área, precisamos das novas medidas:")

                                        try:
                                                nova_base = float(input("Digite a nova base (em metros): "))
                                                nova_altura = float(input("Digite a nova altura (em metros): "))   
                                                novo_entrelinhas = float(input("Digite o novo espaçamento entre as linhas (em metros): "))
                                        except ValueError:
                                                print("Valor inválido. Digite apenas números.")
                                                input("\nPressione Enter para voltar ao menu...")
                                                continue
                                        

                                        if nova_base <= 0 or nova_altura <= 0 or novo_entrelinhas <= 0:
                                                print("Valor inválido. As medidas devem ser maiores que zero.")
                                                input("\nPressione Enter para voltar ao menu...")
                                                continue

                                        nova_area = nova_base * nova_altura
                                        novas_ruas = nova_altura / novo_entrelinhas

                                        areas[id_atualizar] = nova_area
                                        qtd_ruas[id_atualizar] = int(novas_ruas)

                                else:
                                        print("Campo inválido. Por favor, escolha entre cultura, insumo ou área.")
                                        input("\nPressione Enter para voltar ao menu...")
                                        continue
                                

                                cult_atual = culturas[id_atualizar]
                                ins_atual = insumos[id_atualizar]
                                area_atual = areas[id_atualizar]

                                if cult_atual == "Café":
                                        taxa_ha = 600 if ins_atual == "Fertilizante NPK" else 2500 # Se for Café, 600 kg/ha para Fertilizante NPK; 2500 kg/ha para Calcário
                                else: 
                                        taxa_ha = 300 if ins_atual == "Fertilizante NPK" else 2000 # Se for Soja, 300 kg/ha para Fertilizante NPK; 2000 kg/ha para Calcário
                                
                                hectares = area_atual / 10000
                                novo_total_kg = hectares * taxa_ha

                                print("\nRegistro atualizado com sucesso!")
                                print(f"-> NOVO CÁLCULO: Para {area_atual:.2f} m² de {cult_atual}, serão necessários {novo_total_kg:.2f} kg de {ins_atual}.")
                                input("\nPressione Enter para voltar ao menu...")

                        else:
                                print("ID inválido. Por favor, tente novamente.")
                                input("\nPressione Enter para voltar ao menu...")

                        
                                                    
        elif opcao == '4': # Opção para deletar um registro
                if not culturas:
                        print("Nenhum registro encontrado para deletar.")
                        input("\nPressione Enter para voltar ao menu...")
                        
                else:
                        try:
                                id_deletar = int(input("Digite o ID do registro que deseja deletar: "))
                             
                        except ValueError:
                                print("ID inválido. Por favor, digite um número inteiro.")
                                input("\nPressione Enter para voltar ao menu...")
                                    
                        else:
                                if 0 <= id_deletar < len(culturas):
                                        del culturas[id_deletar]
                                        del areas[id_deletar]
                                        del insumos[id_deletar]
                                        del qtd_ruas[id_deletar]

                                        print("Registro deletado com sucesso!")
                                        input("\nPressione Enter para voltar ao menu...")
                                else:
                                        print("ID inválido. Por favor, tente novamente.")
                                        input("\nPressione Enter para voltar ao menu...")


                
        elif opcao == '5': # Opção para sair do programa e salvar os dados em um arquivo CSV
                print("\nSalvando os dados...")

                with open('dados_farmtech.csv', mode='w', newline='', encoding='utf-8') as arquivo:
                        
                        escritor = csv.writer(arquivo)
                        
                        escritor.writerow(['Cultura', 'Area_m2', 'Insumo', 'Qtd_Ruas'])
                        
                        for linha in zip(culturas, areas, insumos, qtd_ruas):
                                escritor.writerow(linha)
                
                print("Dados salvos com sucesso! Encerrando o programa.")
                break
                        

        else:
                print("Opção inválida. Por favor, selecione uma opção entre 1 e 5.")
                input("\nPressione Enter para tentar novamente...")