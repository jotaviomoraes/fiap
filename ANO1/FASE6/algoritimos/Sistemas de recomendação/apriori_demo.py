# %%
# imports
import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules

# %%
# conjunto de dados
df = pd.DataFrame(
    [
        [True, True, False, False, True],
        [False, True, False, True, False],
        [False, True, True, False, False],
        [True, True, False, True, False],
        [True, False, True, False, False],
        [False, True, True, False, False],
        [True, False, True, False, False],
        [True, True, True, False, True],
        [True, True, True, False, False],
    ],
    columns=["Leite", "Pão", "Manteiga", "Café", "Açúcar"],
)
# %%
# # calculando subconjuntos frequentes
subconjuntos_frequentes = apriori(df, min_support=0.2, use_colnames=True)

# calculando regras de associação
regras = association_rules(subconjuntos_frequentes, min_threshold=0.6)

for i, regra in regras.iterrows():
    ant = ", ".join(regra["antecedents"])
    cons = ", ".join(regra["consequents"])
    conf = regra["confidence"]

    print(f"r_{i}: {ant} => {cons}: confiança(r_{i}) = {conf:.2f}")
