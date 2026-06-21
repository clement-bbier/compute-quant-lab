# P01 — Notes de convergence (zone protégée)

> Patches à appliquer par la **session de convergence** uniquement. P01 n'écrit
> que dans `core/pricing/**` et `projects/01_digital_spark_spread/**` ; tout ce
> qui suit touche la zone protégée (`pyproject.toml`, `.github/`, `.gitignore`,
> `.claude/`, `core/utils/`) et a donc été **signalé, pas appliqué**.

## 1. `pyproject.toml` racine — build du noyau Rust
Le subcrate maturin autonome est livré (`core/pricing/_kernel/` : `Cargo.toml`,
`pyproject.toml` local, `src/lib.rs`). Il **compile** (cargo 1.94, pyo3 0.23 +
numpy 0.23, profil release OK). Aujourd'hui le `.pyd` est un artefact **local**
(copié depuis `_kernel/target/release/_kernel.dll` vers `core/pricing/_kernel.pyd`,
git-ignoré).
- **À faire** : unifier le build pour que `pip install -e .` / la wheel embarquent
  `core.pricing._kernel` (maturin + hatchling, ou bascule maturin). Ajouter
  `maturin` aux deps dev.
- **Commande de référence** : `maturin develop --manifest-path core/pricing/_kernel/Cargo.toml`.

## 2. `.github/workflows/ci.yml` — toolchain Rust + parité (d)
Ajouter Rust + `maturin develop` du subcrate + exécuter `pytest -k parity`.
Sans cela, le test de parité Rust↔Python **skip** en CI (il passe en local après
compilation : `np.allclose` bit-exact sur 10 000 points).

## 3. `.gitignore` racine — DVC bloqué sur `data/interim`
`dvc add data/interim/aligned_spark.parquet` échoue :
`ERROR: bad DVC file name '...aligned_spark.parquet.dvc' is git-ignored`.
Cause : le motif `/data/interim/*` ignore **aussi** les pointeurs `*.dvc`, ce qui
contredit le commentaire du `.gitignore` (« le contenu, pas les .dvc »).
- **Fix** : ajouter une exception, p. ex.
  ```gitignore
  !/data/interim/*.dvc
  !/data/processed/*.dvc
  ```
  Sans ce fix, la DoD « données versionnées DVC » est **inatteignable** depuis la
  zone P01 (le script dégrade proprement en `untracked`).

## 4. `core/utils/tracking.py` — MLflow ≥ 3 (owner : core/utils)
MLflow 3.14 met le file store en « maintenance mode » et lève une exception sans
`MLFLOW_ALLOW_FILE_STORE=true`. P01 a posé l'opt-out **localement** dans
`run_pricer.py` (stopgap). À porter dans le util (ou migrer vers
`sqlite:///experiments/mlflow.db`, recommandation MLflow).

## 5. `core/utils/{config,logging}.py` absents (owner : core/utils)
Référencés par les rules mais inexistants (seul `tracking.py` existe). P01 les
contourne (DI dans `core/`, `logging` stdlib dans les scripts projet). À créer.

## 6. `.claude/rules/` — rule unités/fuseau (candidat, prompt P01 §8)
Proposer une rule path-scopée « cohérence unités/fuseau » sur `core/pricing/`.
Point d'application naturel déjà en place : `core/pricing/_timeindex.to_utc_index`
(rejet du naïf, normalisation UTC), testé.

## 7. Emplacement des tests (info, pas un patch)
Les tests du pricer sont dans la racine `tests/` (`test_pricer.py`,
`test_pricer_parity.py`) car la gate `pytest -q` utilise `testpaths=["tests"]`.
**Additifs** : les 3 tests existants restent verts, aucun fichier existant modifié.
Pas de collision attendue avec P08 (fichiers de tests disjoints).

## 8. Données réelles ENTSO-E
`prepare_dataset.py` fetche le réel si `ENTSOE_API_TOKEN` est dans `.env` (à
recopier via `.worktreeinclude`). En session, token absent → **repli synthétique
déterministe** (loggué). Le swap vers le réel est automatique dès le token fourni.

## 9. État de la DoD (prompt §11)
- [x] Tests verts dont anti look-ahead (b) + parité Rust/Python (d) — 18 passed.
- [x] `ruff check .` & `mypy core` verts.
- [x] Run MLflow loggué (params + métriques + SHA) via `core.utils.tracking`.
- [~] Données DVC — **bloqué par §3** (gitignore) ; parquet produit, `untracked`.
- [x] Synthèse écrite (`results/SYNTHESIS.md` + `run_summary.json`).
- [x] Rien écrit hors `core/pricing/` + `projects/01…` (hors artefacts data/MLflow
      générés par le run, git-ignorés). Patches zone protégée listés ci-dessus.
