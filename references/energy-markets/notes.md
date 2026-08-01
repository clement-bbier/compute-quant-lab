# Energy markets & derivatives — notes

> Distilled protocol + pointers. No copyrighted text is copied here — see
> `references/bibliography.md` for full citations.

Referenced by `.claude/skills/spread-trading-playbook`.

## Sources

- **Eydeland, A. & Wolyniec, K.**, *Energy and Power Risk Management* —
  quantitative treatment of power/gas markets: forward curves, volatility
  structure, and the risk-management side of physical commodity trading.
- **Clewlow, L. & Strickland, C.**, *Energy Derivatives: Pricing and Risk
  Management* — pricing methodology for energy derivatives (forwards,
  options, spread options) under the mean-reverting, seasonal dynamics
  typical of power and gas prices.

## The spark spread, and its adaptation here

The classic **spark spread** = electricity revenue - gas cost of generating
that electricity, used by power-plant operators to value and hedge
generation capacity. This lab adapts the same logic into the **digital
spark spread**: compute revenue ($/GPU-h) - the electricity cost of running
that GPU (PUE x power draw x electricity price). The economic intuition
carries over directly — a datacenter operator is, in this framing, running a
plant that converts electricity into a different commodity (compute).

## Practical notes for the energy leg

- Energy data (ENTSO-E) is liquid, deep-history, and hourly — this is the
  well-behaved side of the digital spark spread.
- The energy leg's price dynamics (seasonality, mean reversion, occasional
  spikes) are the reference behavior against which the much younger and more
  volatile compute price series should be judged; see
  `.claude/skills/spread-trading-playbook/SKILL.md` for how this asymmetry
  shapes the strategy.
