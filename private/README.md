# `private/` — zone à edge, JAMAIS versionnée en ligne

> Le repo est **public**. Tout ce qui constitue un **avantage monétisable** (signaux
> qui rapportent, paramètres calibrés gagnants, stratégies d'exécution réelles) vit
> **ici** et n'est **jamais** poussé. Seul ce fichier `README.md` et `.gitkeep` sont suivis.

## Règle (non négociable)
- Le **public** montre l'**infrastructure** et le **benchmark** (impressionnant, vendable
  comme portfolio / data) — **pas l'edge**.
- Le **privé** garde ce qui gagne : un signal committé sur un repo public = **edge mort**
  (tout le monde le voit). C'est la séparation infra (publique) / alpha (privé).

## Conventions gitignorées (voir `.gitignore`)
- Tout `private/**` (sauf ce README + `.gitkeep`).
- Tout fichier `*.private.py`, `*.private.json`, `*.private.parquet` **où qu'il soit**.

## Où mettre quoi
| Type | Emplacement |
|---|---|
| Signal de procurement gagnant, params calibrés | `private/procurement/` |
| Stratégie tradable réelle, seuils optimisés | `private/strategies/` |
| Données/dérivés à edge | `private/data/` ou `*.private.parquet` |
| Brique générique réutilisable (sans edge) | reste dans `core/` (public) |

> En cas de doute : « est-ce que voir ce fichier donne à quelqu'un un avantage que je
> perds ? » → si oui, **privé**.
