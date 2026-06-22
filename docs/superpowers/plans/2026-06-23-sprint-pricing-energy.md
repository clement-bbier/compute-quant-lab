# Sprint « Unité de compte + fondation énergie » — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verrouiller l'unité de compte du spark spread (normalisation FLOPS/Watt +
PUE en prior region-keyed) et poser la fondation énergie multi-marché pluggable avec
ERCOT comme premier marché branché — afin de pouvoir, ensuite, calibrer l'hypothèse
pré-enregistrée L0.

**Architecture:** Deux sous-systèmes **disjoints**, un par worktree branché sur
`integration`. (A) `core/pricing/` : table d'efficacité GPU figée + `PuePrior`
truncated-normal, propagés dans le pricer existant sans casser la parité Rust.
(B) `core/ingestion/energy/` : `Protocol EnergyMarket` + registre key-gated calqué
sur `core/ingestion/providers/` (W1/W2), ERCOT branché via `gridstatus`. La couche
calibration L0 (P07) est un **plan suivant**, gaté sur la livraison de B.

**Tech Stack:** Python ≥ 3.11, `uv`, pytest (TDD), ruff + mypy, pandas/numpy,
`gridstatus` (ERCOT), `scipy.stats` (truncated-normal). Rust optionnel inchangé.

**Contrat amont :** [L0 ERCOT](../specs/2026-06-23-L0-ercot-grid-stress-preregistration.md)
(signée, figée). Le prior PUE et le seuil τ y sont déjà fixés.

---

## Partition de propriété (anti-collision merge)

| Worktree | Branche | Possède (écrit UNIQUEMENT ici) |
|---|---|---|
| `../lab-pricing_efficiency` | `feature/P15-pricing_efficiency` | `core/pricing/` |
| `../lab-energy_ingestion` | `feature/P16-energy_ingestion` | `core/ingestion/energy/` (nouveau sous-paquet) |

Zone protégée (jamais touchée en worktree, passe par convergence) : `CLAUDE.md`,
`.claude/`, `.mcp.json`, `pyproject.toml`. Une dépendance nouvelle (`gridstatus`,
`scipy`) se **prépare en patch** et remonte à la convergence.

---

# SOUS-SYSTÈME A — `core/pricing` : unité de compte

### File Structure (A)

- Create: `core/pricing/efficiency.py` — table figée GPU → (TFLOPS FP16 dense, TDP W),
  + `flops_per_watt`. Responsabilité unique : référentiel d'efficacité, zéro logique.
- Create: `core/pricing/pue_prior.py` — `PuePrior` (truncated-normal region-keyed) :
  point estimate + bornes de sensibilité. Responsabilité unique : le prior PUE.
- Create: `tests/test_efficiency.py`, `tests/test_pue_prior.py`,
  `tests/test_normalized_spread.py` — **convention fondation réelle : `testpaths = ["tests"]`
  à la racine** (les tests P01 vivent dans `tests/`, pas dans `tests/`).
- Modify: `core/pricing/power_model.py` — accepter un `PuePrior` comme source du PUE
  (rétro-compatible : un float reste accepté).
- Modify: `core/pricing/pricer.py` — exposer un spread **normalisé** par TFLOP et les
  **bandes** low/high issues du prior PUE, sans changer le chemin central ni la parité Rust.

### Task A1 : Table d'efficacité GPU figée

**Files:** Create `core/pricing/efficiency.py`, `tests/test_efficiency.py`

- [ ] **Step 1 — Test qui échoue** (`test_efficiency.py`) :

```python
import math
import pytest
from core.pricing.efficiency import GPU_SPECS, flops_per_watt, tflops_fp16


def test_known_specs_present():
    for gpu in ("A100", "H100", "H200", "B200"):
        assert gpu in GPU_SPECS


def test_flops_per_watt_h100():
    # H100 SXM : 989.5 TFLOPS FP16 Tensor dense @ 700 W -> ~1.414 TFLOPS/W
    assert flops_per_watt("H100") == pytest.approx(989.5 / 700.0, rel=1e-6)


def test_blackwell_more_efficient_than_hopper():
    assert flops_per_watt("B200") > flops_per_watt("H100") > flops_per_watt("A100")


def test_unknown_gpu_raises():
    with pytest.raises(KeyError):
        tflops_fp16("RTX_FANTASY")
```

- [ ] **Step 2 — Lancer, vérifier l'échec** : `uv run pytest tests/test_efficiency.py -v` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3 — Implémentation minimale** (`efficiency.py`) :

```python
"""Référentiel figé d'efficacité GPU (convention unique : TFLOPS FP16 Tensor dense).

Convention documentée et non magique (rule python-quality) : tout chiffre vient des
datasheets constructeur, en FP16 Tensor **dense** (sans sparsité), TDP nominal du
module SXM. Sert de dénominateur commun pour comparer le spread entre GPU.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GpuSpec:
    """Spec d'efficacité d'un GPU. `tflops_fp16` = FP16 Tensor dense ; `tdp_w` = watts."""

    tflops_fp16: float
    tdp_w: float


# Sources : datasheets NVIDIA (SXM, FP16 Tensor dense). À réviser via fiche dédiée.
GPU_SPECS: dict[str, GpuSpec] = {
    "A100": GpuSpec(tflops_fp16=312.0, tdp_w=400.0),
    "H100": GpuSpec(tflops_fp16=989.5, tdp_w=700.0),
    "H200": GpuSpec(tflops_fp16=989.5, tdp_w=700.0),  # même calcul, plus de mémoire
    "B200": GpuSpec(tflops_fp16=2250.0, tdp_w=1000.0),
}


def tflops_fp16(gpu: str) -> float:
    """TFLOPS FP16 Tensor dense du GPU (lève KeyError si inconnu)."""
    return GPU_SPECS[gpu].tflops_fp16


def flops_per_watt(gpu: str) -> float:
    """Efficacité TFLOPS par watt (TDP nominal). Dénominateur d'efficacité énergétique."""
    spec = GPU_SPECS[gpu]
    return spec.tflops_fp16 / spec.tdp_w
```

- [ ] **Step 4 — Lancer, vérifier le succès** : `uv run pytest tests/test_efficiency.py -v` → PASS.
- [ ] **Step 5 — Commit** : `git add core/pricing/efficiency.py tests/test_efficiency.py && git commit -m "feat(pricing): table d'efficacité GPU figée (FLOPS/Watt FP16 dense)"`

### Task A2 : `PuePrior` truncated-normal region-keyed

**Files:** Create `core/pricing/pue_prior.py`, `tests/test_pue_prior.py`

- [ ] **Step 1 — Test qui échoue** :

```python
import pytest
from core.pricing.pue_prior import PuePrior, ERCOT_TEXAS_PRIOR


def test_point_estimate_is_mu():
    p = PuePrior(mu=1.45, sigma=0.15, low=1.2, high=1.8)
    assert p.point_estimate() == pytest.approx(1.45)


def test_sensitivity_bounds_are_support():
    p = PuePrior(mu=1.45, sigma=0.15, low=1.2, high=1.8)
    assert p.sensitivity_bounds() == (1.2, 1.8)


def test_samples_respect_support_and_physics():
    p = PuePrior(mu=1.45, sigma=0.15, low=1.2, high=1.8)
    xs = p.sample(10_000, seed=7)
    assert xs.min() >= 1.2 and xs.max() <= 1.8
    assert (xs >= 1.0).all()  # PUE >= 1 par définition physique


def test_texas_prior_matches_L0():
    assert ERCOT_TEXAS_PRIOR.point_estimate() == pytest.approx(1.45)
    assert ERCOT_TEXAS_PRIOR.sensitivity_bounds() == (1.2, 1.8)
```

- [ ] **Step 2 — Échec attendu** : `uv run pytest tests/test_pue_prior.py -v` → FAIL.

- [ ] **Step 3 — Implémentation** (`pue_prior.py`) :

```python
"""Prior PUE region-keyed (truncated-normal), conforme à la fiche L0.

Prior **strict** : jamais mis à jour par les prix (interdit de fit-to-price). Fournit
un point estimate (μ, chemin de pricing central) et des bornes de sensibilité (support).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import truncnorm


@dataclass(frozen=True)
class PuePrior:
    """Distribution truncated-normal sur le PUE (≥ 1 par construction via `low`)."""

    mu: float
    sigma: float
    low: float
    high: float

    def __post_init__(self) -> None:
        if self.low < 1.0:
            raise ValueError("PUE >= 1.0 : `low` ne peut être < 1.0")
        if not (self.low <= self.mu <= self.high):
            raise ValueError("mu doit être dans [low, high]")

    def _dist(self) -> truncnorm:
        a = (self.low - self.mu) / self.sigma
        b = (self.high - self.mu) / self.sigma
        return truncnorm(a, b, loc=self.mu, scale=self.sigma)

    def point_estimate(self) -> float:
        """μ — le PUE central utilisé pour le spread de référence."""
        return self.mu

    def sensitivity_bounds(self) -> tuple[float, float]:
        """Support [low, high] — bornes des bandes de sensibilité du pricing."""
        return (self.low, self.high)

    def sample(self, n: int, *, seed: int) -> np.ndarray:
        """Tirage reproductible (déterminisme exigé par le labo)."""
        return self._dist().rvs(size=n, random_state=np.random.default_rng(seed))


# Conforme L0 §8 (Texas centré plus haut pour le refroidissement).
ERCOT_TEXAS_PRIOR = PuePrior(mu=1.45, sigma=0.15, low=1.2, high=1.8)
```

- [ ] **Step 4 — Succès** : `uv run pytest tests/test_pue_prior.py -v` → PASS.
- [ ] **Step 5 — Commit** : `git commit -am "feat(pricing): PuePrior truncated-normal region-keyed (L0 §8)"`

### Task A3 : `ServerPowerModel` accepte un `PuePrior` (rétro-compatible)

**Files:** Modify `core/pricing/power_model.py`, add tests in `tests/test_pue_prior.py`

- [ ] **Step 1 — Test qui échoue** :

```python
from core.pricing.power_model import ServerPowerModel
from core.pricing.pue_prior import ERCOT_TEXAS_PRIOR

def test_power_model_accepts_prior():
    m = ServerPowerModel(tdp_w=700, pue=ERCOT_TEXAS_PRIOR, n_gpus=8)
    assert m.pue() == ERCOT_TEXAS_PRIOR.point_estimate()

def test_power_model_still_accepts_float():
    m = ServerPowerModel(tdp_w=700, pue=1.5, n_gpus=8)
    assert m.pue() == 1.5
```

- [ ] **Step 2 — Échec** : `uv run pytest tests/test_pue_prior.py -v` → FAIL.
- [ ] **Step 3 — Implémentation** : dans `power_model.py`, accepter `pue: float | PuePrior`.
  Stocker ; `pue()` retourne `self._pue.point_estimate()` si c'est un `PuePrior`, sinon le float.
  Conserver la validation `pue >= 1.0` sur le float ; pour un prior, la validation vit dans `PuePrior`.

```python
# en tête
from core.pricing.pue_prior import PuePrior

# __init__ : remplacer le paramètre `pue: float`
def __init__(self, tdp_w: float, pue: float | PuePrior, n_gpus: int) -> None:
    ...
    if isinstance(pue, PuePrior):
        self._pue_value = pue.point_estimate()
        self._pue_prior: PuePrior | None = pue
    else:
        if pue < 1.0:
            raise ValueError("pue doit être ≥ 1.0 (le datacenter consomme ≥ l'IT)")
        self._pue_value = pue
        self._pue_prior = None

def pue(self) -> float:
    return self._pue_value

def pue_bounds(self) -> tuple[float, float] | None:
    """Bornes de sensibilité si un prior est fourni, sinon None."""
    return self._pue_prior.sensitivity_bounds() if self._pue_prior else None
```

- [ ] **Step 4 — Succès** : `uv run pytest tests/ -v` → PASS (toute la suite pricing).
- [ ] **Step 5 — Commit** : `git commit -am "feat(pricing): ServerPowerModel accepte un PuePrior (rétro-compatible float)"`

### Task A4 : Spread normalisé par TFLOP + bandes PUE

**Files:** Modify `core/pricing/pricer.py`, create `tests/test_normalized_spread.py`

- [ ] **Step 1 — Test qui échoue** :

```python
import pandas as pd
from core.pricing.pricer import SparkSpreadPricer
from core.pricing.power_model import ServerPowerModel
from core.pricing.pue_prior import ERCOT_TEXAS_PRIOR
from core.pricing.fx import IdentityFx  # à confirmer : fx neutre existant
from core.pricing.sources import DataFramePriceSource
from core.pricing.efficiency import tflops_fp16

def _toy_source():
    idx = pd.date_range("2026-01-01", periods=3, freq="h", tz="UTC")
    energy = pd.DataFrame({"ERCOT": [50.0, 50.0, 50.0]}, index=idx)
    compute = pd.DataFrame({"H100": [2.0, 2.0, 2.0]}, index=idx)
    return DataFramePriceSource(energy, compute)

def test_normalized_spread_divides_by_tflops():
    pricer = SparkSpreadPricer(ServerPowerModel(700, ERCOT_TEXAS_PRIOR, 8), IdentityFx())
    res = pricer.price(_toy_source(), gpu="H100", region="ERCOT")
    norm = pricer.normalized_spread(res)
    assert norm.iloc[0] == res.spread.iloc[0] / tflops_fp16("H100")

def test_pue_bands_bracket_central_cost():
    pricer = SparkSpreadPricer(ServerPowerModel(700, ERCOT_TEXAS_PRIOR, 8), IdentityFx())
    low, high = pricer.pue_sensitivity(_toy_source(), gpu="H100", region="ERCOT")
    res = pricer.price(_toy_source(), gpu="H100", region="ERCOT")
    # PUE plus haut => coût énergie plus haut => spread plus bas
    assert high.spread.iloc[0] <= res.spread.iloc[0] <= low.spread.iloc[0]
```

- [ ] **Step 2 — Échec** : `uv run pytest tests/test_normalized_spread.py -v` → FAIL. *(Vérifier le nom réel de la FX neutre dans `core/pricing/fx.py` ; ajuster l'import si besoin.)*
- [ ] **Step 3 — Implémentation** : ajouter à `SparkSpreadPricer` deux méthodes **pures**, sans toucher au chemin central `price()` (parité Rust intacte) :
  - `normalized_spread(res: SpreadResult) -> pd.Series` : `res.spread / tflops_fp16(res.gpu)`.
  - `pue_sensitivity(source, gpu, region) -> tuple[SpreadResult, SpreadResult]` : re-price aux bornes `low`/`high` du prior en injectant temporairement un `ServerPowerModel` au PUE de borne (réutilise le kernel existant).
- [ ] **Step 4 — Succès** : `uv run pytest tests/ -v` → PASS.
- [ ] **Step 5 — Vérifier la non-régression parité Rust** : `uv run pytest tests -k parity -v` → PASS si kernel Rust buildé, sinon `skipped` (état baseline) — le chemin central est inchangé.
- [ ] **Step 6 — Commit** : `git commit -am "feat(pricing): spread normalisé par TFLOP + bandes de sensibilité PUE"`

---

# SOUS-SYSTÈME B — `core/ingestion/energy` : fondation multi-marché + ERCOT

### File Structure (B)

- Create: `core/ingestion/energy/__init__.py`
- Create: `core/ingestion/energy/base.py` — `Protocol EnergyMarket` + dataclasses
  (`ReserveForecast`, `RtmPrice`) + registre key-gated (calqué sur `providers/base.py`).
- Create: `core/ingestion/energy/ercot.py` — implémentation ERCOT via `gridstatus`.
- Create: `core/ingestion/energy/tests/conftest.py`, `test_registry.py`,
  `test_ercot_parsers.py`, `test_fetch_live.py` (marqué `@pytest.mark.live`).

### Task B0 : Vérifier la surface API `gridstatus` ERCOT (AVANT de coder contre elle)

- [ ] **Step 1** : `uv add gridstatus` **en patch local** (la dépendance remonte à la
  convergence — ne pas committer `pyproject.toml` depuis le worktree).
- [ ] **Step 2** : dans un REPL `uv run python`, confirmer les méthodes réelles et
  **les heures de publication** (exigence point-in-time L0 §2) :

```python
import gridstatus
iso = gridstatus.Ercot()
# Confirmer noms exacts : get_rtm_spp / get_spp / get_load_forecast /
# get_capacity_committed_and_available, colonnes, fuseau, profondeur historique.
print([m for m in dir(iso) if not m.startswith("_")])
```

- [ ] **Step 3** : consigner dans `core/ingestion/energy/ercot.py` (docstring de tête)
  les noms de méthodes/colonnes confirmés + l'heure de publication du rapport de
  prévision retenu pour le cutoff 18:00 J-1. **Ce relevé conditionne la causalité L0.**

> Tâche assignée au `data-engineer`. Les tâches B1+ ci-dessous codent contre la surface
> confirmée en B0 ; si un nom diffère, on ajuste les parsers — pas la fiche L0.

### Task B1 : `Protocol EnergyMarket` + registre key-gated

**Files:** Create `core/ingestion/energy/base.py`, `.../tests/test_registry.py`

- [ ] **Step 1 — Test qui échoue** :

```python
import pytest
from core.ingestion.energy.base import EnergyMarket, register_market, get_market, available_markets

def test_register_and_get():
    @register_market("dummy")
    class _Dummy:
        name = "dummy"
        def rtm_price(self, start, end): ...
        def reserve_forecast(self, start, end): ...
    assert "dummy" in available_markets()
    assert isinstance(get_market("dummy"), EnergyMarket)

def test_unknown_market_raises():
    with pytest.raises(KeyError):
        get_market("atlantis")
```

- [ ] **Step 2 — Échec** : `uv run pytest core/ingestion/energy/tests/test_registry.py -v` → FAIL.
- [ ] **Step 3 — Implémentation** : reproduire le pattern de `core/ingestion/providers/base.py`
  (lire ce fichier d'abord) : `Protocol EnergyMarket` avec `rtm_price(start, end) -> pd.Series`
  et `reserve_forecast(start, end) -> pd.DataFrame` ; décorateur `register_market(key)` ;
  `get_market`, `available_markets`. Key-gated : un marché nécessitant une clé n'est listé
  que si la clé est présente (ERCOT = public, toujours listé).
- [ ] **Step 4 — Succès** ; **Step 5 — Commit** : `feat(ingestion): fondation énergie pluggable (Protocol + registre)`.

### Task B2 : Connecteur ERCOT — parsers point-in-time (tests sur fixtures)

**Files:** Create `core/ingestion/energy/ercot.py`, `.../tests/test_ercot_parsers.py`,
fixtures figées sous `.../tests/fixtures/` (échantillons réels capturés en B0).

- [ ] **Step 1 — Test qui échoue** : sur une fixture CSV figée de `get_rtm_spp`, vérifier
  que le parser retourne une `pd.Series` UTC tz-aware triée, en $/MWh, sans NaN injecté,
  et que `reserve_forecast` horodate à l'**heure de publication** (pas l'heure cible) →
  garantit le point-in-time.
- [ ] **Step 2 — Échec** ; **Step 3 — Implémentation** des parsers (pur, I/O isolée) ;
  **Step 4 — Succès** ; **Step 5 — Commit** : `feat(ingestion): connecteur ERCOT (parsers point-in-time)`.

### Task B3 : Smoke test live ERCOT (réel, marqué)

**Files:** `.../tests/test_fetch_live.py`

- [ ] **Step 1** : test `@pytest.mark.live` qui tire 2 jours réels de RTM + prévision,
  asserte volumétrie > 0, monotonie temporelle, fuseau correct. Exclu de la CI par défaut
  (réseau), lancé à la demande : `uv run pytest -m live -v`.
- [ ] **Step 2 — Commit** : `test(ingestion): smoke live ERCOT (réel, gated par marker)`.

### Gate de sortie B (avant convergence)

- [ ] `uv run pytest core/ingestion/energy -v` vert (hors `live`).
- [ ] Passe **`data-quality-auditor`** sur un échantillon réel (gaps, outliers, intégrité
  point-in-time de la prévision).
- [ ] `ruff check . && mypy core` verts.

---

# DIFFÉRÉ — Calibration L0 (P07), plan suivant

Dépend de la livraison de B (données ERCOT réelles) et de A (unité de compte). **Ne
démarre pas dans ce sprint.** Sera un plan dédié `…-p07-ercot-calibration.md` couvrant :
construction des features stress (sur `core/features` existant), entraînement/holdout
purged+embargo, baseline climatologique, PR-AUC, passe `backtest-pitfalls` + `risk-validator`,
run MLflow. Tout est déjà cadré par la fiche L0.

---

## Self-Review (couverture spec L0 + sprint)

- **L0 §3 prédicteur gelé** → couvert par B (reserve_forecast) ; le gradient net-load est
  une feature de la couche calibration différée (P07), pas de B. ✔ cohérent.
- **L0 §8 prior PUE** → Tasks A2/A3/A4 (μ=1.45, support [1.2,1.8], jamais fité). ✔
- **Normalisation FLOPS/Watt** → Tasks A1/A4. ✔
- **Fondation multi-marché** → Task B1 (Protocol + registre), ERCOT en B2. ✔
- **Provenance réel/simulé** → ERCOT 100 % réel ; aucun flag simulated requis. ✔
- **Parité Rust** → A4 Step 5 (chemin central `price()` inchangé). ✔
- **Gaps connus** : la calibration L0 elle-même est explicitement différée (plan suivant) —
  ce n'est pas un trou, c'est le séquençage gaté sur la donnée. ✔
- **Placeholders** : import FX neutre (`IdentityFx`) à confirmer dans `fx.py` (noté en
  A4 Step 2) ; surface `gridstatus` à confirmer en B0 avant de coder B1+. Honnête, borné.
