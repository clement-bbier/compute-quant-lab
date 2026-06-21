# Compute Quant Lab

Labo de recherche quant traitant le **compute** (location de GPU) comme une classe
d'actifs, arbitré contre sa matière première : l'**électricité** (*digital spark spread*).

## Démarrage
```bash
uv sync --extra dev
uv run pytest          # vérifie le module de pricing
pre-commit install
```

## Structure
Voir `CLAUDE.md` (index complet du labo, organisation, sources, agents).

## Orchestration agentique
Le dossier `.claude/` configure le labo pour un travail agentique : rules (qualité),
skills (procédures), agents (le « personnel »), hooks (garde-fous déterministes).
