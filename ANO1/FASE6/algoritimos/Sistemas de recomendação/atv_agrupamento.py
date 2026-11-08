# %%
# imports
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

# %%
# leitura
df = pd.read_csv("spotify_tracks_dataset.csv")
# %%
# classificação dos atributos
num_feat = df.select_dtypes(include=["number"]).columns.tolist()
# %%
# normalização
scaler = StandardScaler()
df[num_feat] = scaler.fit_transform(df[num_feat])
# %%
# análise de correlação
plt.subplots(figsize=(12, 8))
sns.heatmap(
    df.drop(columns=["id", "name", "artists", "release_date", "year"]).corr(),
    annot=True,
    square=True,
)
plt.show()


# %%
#  Seleção de Atributos
features = [
    "valence",
    "acousticness",
    "danceability",
    "duration_ms",
    "energy",
    "instrumentalness",
    "liveness",
    "loudness",
    "speechiness",
    "tempo",
]
X = df[features]


# %%
# clusterização
dbscan = DBSCAN(eps=0.5, min_samples=20)
clusters = dbscan.fit_predict(X)
labels = dbscan.labels_
n_clusters_ = len(set(labels)) - (1 if -1 in labels else 0)
n_noise_ = list(labels).count(-1)

print(f"Número estimado de clusters: {n_clusters_}")
print(f"Número estimado de pontos de ruído: {n_noise_}")
if n_clusters_ > 1:
    score = silhouette_score(X, labels)
    print(f"Coeficiente de Silhueta: {score:.4f}")
