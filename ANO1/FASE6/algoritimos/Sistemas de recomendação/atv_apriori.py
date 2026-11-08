# %%
# imports
import pandas as pd
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import apriori, association_rules

# %%
# leitura
df = pd.read_csv("spotify_playlist_dataset.csv", on_bad_lines="skip")
df.columns = df.columns.str.replace('"', "").str.strip()
df = df.dropna(subset=["artistname"])
# %%
# amostragem e filtragem de playlists
unique_playlists = df["playlistname"].unique()
sample_pl_names = pd.Series(unique_playlists).sample(n=500, random_state=42)
df_sample = df[df["playlistname"].isin(sample_pl_names)]

artist_counts = df_sample.groupby("artistname")["playlistname"].nunique()
artistas_frequentes = artist_counts[artist_counts >= 5].index
df_sample = df[df["artistname"].isin(artistas_frequentes)]

df_list = (
    df_sample.groupby("playlistname")["artistname"]
    .apply(lambda x: list(set(x)))
    .reset_index()
)
# %%
# one-hot encoding
te = TransactionEncoder()
te_ary = te.fit(df_list["artistname"]).transform(df_list["artistname"])
df_ohe = pd.DataFrame(te_ary, columns=te.columns_)
# %%
# mineração de regras de associação
freq_subsets = apriori(df_ohe, min_support=0.025, use_colnames=True)
rules = association_rules(freq_subsets, min_threshold=0.1)
# %%
# sugestão de artistas para quem ouve Rihanna
recommendations = rules[rules["antecedents"] == frozenset({"Rihanna"})]
recommendations = recommendations.sort_values(by="lift", ascending=False)
recommendations["consequents"] = recommendations["consequents"].apply(
    lambda x: list(x)[0]
)
print("Artistas recomendados para quem ouve Rihanna:")
for idx, row in recommendations.iterrows():
    print(row["consequents"])
