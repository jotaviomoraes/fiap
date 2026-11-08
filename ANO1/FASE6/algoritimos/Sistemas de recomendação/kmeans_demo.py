# %%
# imports
import numpy as np
import matplotlib.pyplot as plt
from sklearn.datasets import make_blobs
from sklearn.cluster import KMeans
from sklearn import metrics

# %%
# dados
centers = [[1, 1], [-1, -1], [1, -1]]
X, labels_true = make_blobs(
    n_samples=750, centers=centers, cluster_std=0.4, random_state=0
)

plt.scatter(X[:, 0], X[:, 1])
plt.title("Dados Brutos")
plt.show()

# %%
# kmeans
n_clusters_ = 3
kmeans = KMeans(n_clusters=n_clusters_, random_state=0, n_init=10).fit(X)

labels = kmeans.labels_
cluster_centers = kmeans.cluster_centers_

# %%
# visualização e métricas
print(f"Coef. de Silhueta: {metrics.silhouette_score(X, labels):.3f}")

unique_labels = set(labels)
colors = [plt.cm.Spectral(each) for each in np.linspace(0, 1, len(unique_labels))]

plt.figure(figsize=(8, 6))

for k, col in zip(unique_labels, colors):
    class_member_mask = (labels == k)
    xy = X[class_member_mask]
    plt.plot(
        xy[:, 0],
        xy[:, 1],
        "o",
        markerfacecolor=tuple(col),
        markeredgecolor="k",
        markersize=6,
        label=f"Cluster {k}"
    )

plt.plot(
    cluster_centers[:, 0],
    cluster_centers[:, 1],
    "X",
    markerfacecolor="red",
    markeredgecolor="black",
    markersize=15,
    markeredgewidth=2,
    label="Centroides"
)

plt.title(f"Agrupamento com K-Means: {n_clusters_} grupos")
plt.legend()
plt.show()