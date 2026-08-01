---
name: new-research-project
description: Scaffolds a new research project under projects/ with the lab's standard structure. To be invoked to start a project (e.g. "new project on GPU price volatility").
---
# New Research Project

1. Ask for a short number/name (e.g. `02_gpu_vol_term_structure`).
2. Create `projects/NN_name/` with: `CLAUDE.md`, `src/`, `notebooks/`, `results/`, `dashboard/`.
3. The local `CLAUDE.md` describes: the specific thesis, the data used, the
   current progress, the key results. It does NOT duplicate the global glossary.
4. Reuse `core/` as much as possible; whatever becomes generic moves up into `core/`.
5. Add a line to the §4 "project index" of the root CLAUDE.md.
