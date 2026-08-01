# Statistical arbitrage — notes

> Distilled protocol + pointers. No copyrighted text is copied here — see
> `references/bibliography.md` for full citations.

Referenced by `.claude/skills/cointegration-analysis` and
`.claude/skills/spread-trading-playbook`.

## Cointegration: why it matters here

Two series can be correlated by chance (spurious correlation) without any
lasting relationship. Cointegration tests for a genuine long-run equilibrium
relationship between two non-stationary series — it is the statistical
foundation for shorting/longing a spread. Never trade a spread without
having tested it.

- **Engle & Granger (1987)** — the founding two-series test: regress y on x,
  then test the residual for stationarity (ADF). A stationary residual means
  the pair is cointegrated. Simple, but sensitive to which series is chosen
  as the regressor.
- **Johansen** — the multivariate test (>= 2 series), more robust: estimates
  the cointegration vector and the number of cointegrating relationships
  directly, without an arbitrary left-hand-side choice. Preferred whenever
  more than a pair is involved.
- **Avellaneda & Lee (2010)**, *Statistical Arbitrage in the U.S. Equities
  Market* — applies the mean-reversion machinery (PCA/ETF-based factors,
  OU-process half-life) at production scale; the half-life estimation method
  used in the cointegration-analysis skill traces back to this line of work.
- **Chan, E.**, *Algorithmic Trading: Winning Strategies and Their
  Rationale* — the practitioner's playbook for turning a cointegrated pair
  into an executable strategy (entry/exit thresholds, sizing, regime breaks);
  the structure of `spread-trading-playbook` follows this reasoning.

## The one-line protocol

1. Test each raw series for stationarity (ADF + KPSS) — prices are typically I(1).
2. Test the pair for cointegration (Engle-Granger for 2 series, Johansen for >= 2).
3. The spread is the stationary linear combination the test produces — that
   is what gets traded, not the raw prices.
4. Estimate the mean-reversion half-life via an Ornstein-Uhlenbeck fit.
5. Re-test on rolling windows: cointegration can break down (regime change).

Full step-by-step with tooling: `.claude/skills/cointegration-analysis/SKILL.md`.
