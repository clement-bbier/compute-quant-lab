---
paths:
  - "core/ingestion/**"
  - "core/pricing/**"
  - "projects/**"
---
# Frontière réel / simulé (jamais de confusion)

- Toute courbe forward / future construite par modèle est SIMULÉE et DOIT porter
  un drapeau explicite **non optionnel** (ex. `Curve.simulated: bool`).
- Les futures compute CME sont annoncés mais NON listés (revue réglementaire) :
  toute courbe forward compute est donc simulée, jamais servie comme réelle.
- Distinguer dans le code ET les logs le RÉEL (ENTSO-E/PJM, spot Silicon Data) du
  SIMULÉ. Un test DOIT échouer si le drapeau réel/simulé est absent.
- La jambe énergie et le spot compute sont réels ; ne jamais les mélanger avec une
  série simulée sans étiquetage explicite.
