# P10 — Patches pour la session de convergence

> P10 n'écrit que dans `projects/10_portfolio_execution/`. Les modifications de la **zone
> protégée** (`pyproject.toml`, `.claude/`, `CLAUDE.md` racine, `.mcp.json`, `core/`) sont
> listées ici et appliquées **uniquement** par la session qui pilote `integration`.

## 1. `pyproject.toml` — collecte des tests P10
Les tests projet ne sont pas collectés par défaut (`testpaths = ["tests"]`). Ajouter un job CI
isolé pour `projects/10_portfolio_execution/tests` (même schéma que les autres projets : chaque
dossier lancé séparément à cause des `conftest` à import nu). Exemple de commande CI :
```bash
uv run pytest projects/10_portfolio_execution/tests
```

## 2. Brancher les vrais signaux P02/P06/P09
Remplacer les mocks (`signals.py`) par des adaptateurs derrière le **même** Protocol
`SignalProducer` (`name`, `provenance`, `signal(view) -> float ∈ [-1, 1]`) :
- **P02** (mean-reversion) → adaptateur du z-score à hystérésis (déjà un `Strategy` P08).
- **P06** (futures/dérivés) → vue directionnelle du carry/yield implicite.
- **P09** (ML) → sortie du modèle normalisée dans [-1, 1].
Aucun changement attendu dans `desk.py`/`portfolio.py`/`execution.py` (c'est le but du découplage).
Mettre à jour `provenance.simulated=False` quand le signal est réel et que ses données le sont.

## 3. Agent `risk-validator` (absent du roster)
Le labo prévoit cet **adversaire** (CLAUDE.md §6) mais l'agent n'existe pas encore dans
`.claude/agents/` (constat partagé avec P02). À créer en convergence via `agent-architect`. Son
mandat sur P10 : **attaquer le PnL net agrégé** (pas le brut) — corrélations entre signaux
ignorées par l'inverse-vol, coûts sous-estimés, sur-confiance composite (cf. RISK_REVIEW.md §5).

## 4. Palier institutionnel (backlog, pas PoC)
- `WeightScheme` → implémenter `ERCScheme` (risk-parity corrélation-aware, covariance
  point-in-time). Le seam est déjà en place (`portfolio.py::ERCScheme` lève `NotImplementedError`).
- Si l'optimiseur devient générique et réutilisable → le remonter dans `core/` (principe
  PoC → fondation), via la convergence.
- Capacité / limites desk / exécution live ; deflated Sharpe et walk-forward sur signaux réels.

## 5. Référence (optionnel)
Déléguer à `literature-scout` une revue (risk parity / ERC, modèles d'impact Almgren-Chriss,
construction de portefeuille robuste) → `references/` (module possédé par `feature/research`).
