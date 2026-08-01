---
name: market-scan
description: Dispatches a swarm of intelligence-gathering subagents in parallel to map the emerging compute market, each on a disjoint facet. To be invoked for a massive information-gathering session.
---
# Market Scan — parallel intelligence swarm

Goal: gather as much reliable information as possible on compute as an asset class,
in parallel, without redundancy. The agents collect and synthesize; they never write
code.

## Facets (DISJOINT sub-questions — one per agent)
Launch one `literature-scout` subagent per facet, each with a targeted brief:

1. **GPU market structure**: players (Vast.ai, RunPod, hyperscalers), pricing
   mechanisms, liquidity, fragmentation, transparency.
2. **Compute forward / futures markets**: do forward contracts, marketplaces,
   or indices exist? Who prices compute forward?
3. **Energy price dynamics**: drivers of EU spot electricity, gas/weather/renewable links,
   regional spreads (Dunkirk, etc.).
4. **Comparable asset classes**: how other "digital commodities" or
   electricity itself have been financialized — analogies and limits.
5. **Academic literature**: recent papers (arXiv, SSRN) on compute pricing,
   energy/compute arbitrage, the digital spark spread.
6. **Regulatory framework / risks**: what could constrain a compute desk.

## Rules
- Each agent PARAPHRASES, copies no copyrighted text, and cites its sources.
- Each agent returns a ranked synthesis: "what actually matters for us"
  first.
- Deduplicate at convergence: the pilot session merges the syntheses into
  `references/` (one file per facet) and flags contradictions between agents.

## Cadence
Market-scan is AD HOC (it costs tokens). Rerun it when the market moves,
not continuously. Start with 4-6 disjoint facets, no more.
