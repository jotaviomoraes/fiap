import os

from colheitas import calcular_perda, exibir_resultados, pedir_numero, pedir_velocidade, pedir_clima, gerar_recomendacao, faixas_velocidade
from arquivo import carregar_historico, salvar_historico, salvar_relatorio
from banco import inserir_registro, listar_registros


def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def menu():
    while True:
        limpar_tela()
        print("\n- Sistema de colheita de cana de açúcar -\n")
        print("1. Registrar nova colheita (Salvar no histórico e banco Oracle)")
        print("2. Ver histórico de colheitas (Salvo em JSON)")
        print("3. Exportar relatório (Salvar em TXT)")
        print("4. Ver registro no banco Oracle")
        print("5. Sair (Encerrar o programa)")

        opcao = input("\nEscolha uma opção: ").strip()
        limpar_tela()

        if opcao == '1':
            area = pedir_numero("Digite a área colhida (em hectares): ")
            producao = pedir_numero("Digite a produção estimada da área (em toneladas): ")
            velocidade = pedir_velocidade()
            clima = pedir_clima()
            limpar_tela()

            registro = calcular_perda(area, producao, velocidade, clima)
            gerar_recomendacao(registro['faixa_velocidade'], faixas_velocidade, clima, registro["percentual_perda"])   
            
            historico = carregar_historico()
            historico.append(registro)
            salvar_historico(historico)
            if inserir_registro(registro):
                print("\nColheita registrada com sucesso!")
            else:
                print("\nColheita salva no histórico JSON, mas não no banco Oracle.")
        
        elif opcao == '2':
            historico = carregar_historico()
            if historico:
                exibir_resultados(historico)
            else:
                print("\nNenhuma colheita registrada ainda.")

        elif opcao == '3':
            historico = carregar_historico()
            if historico:
                salvar_relatorio(historico)
            else:
                print("\nNenhuma colheita registrada para exportar.")


        elif opcao == '4':
            registros = listar_registros()
            if registros:
                exibir_resultados(registros)
            else:
                print("\nNenhum registro encontrado no banco Oracle.")        

        elif opcao == '5':
            print("\nEncerrando o programa.")
            break

        else:
            print("\nOpção inválida. Tente novamente.")

        input("\nPressione Enter para continuar...")
            

menu()