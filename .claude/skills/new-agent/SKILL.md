---
name: new-agent
description: "Protocol for building an orchestration mechanism (subagent, skill, rule, or hook) via the agent-architect meta-agent. To be invoked to create or revise a lab employee. Trigger: /new-agent."
---
# New Agent — construction protocol

> No agent/skill/rule/hook is created by hand. This procedure is executed
> by (or for) the `agent-architect` agent. It is idempotent: rerun, it
> breaks nothing and proposes a diff rather than an overwrite.

## 1. Frame the single responsibility
State the mission in one sentence. If the sentence contains "and" joining two
distinct missions → **split** into two mechanisms. A catch-all is a refusal.

## 2. Choose the mechanism
| Need | Mechanism | Location |
|---|---|---|
| A role that works in isolation and returns a synthesis | **subagent** | `.claude/agents/X.md` |
| A reusable method/playbook invoked on demand | **skill** | `.claude/skills/X/SKILL.md` |
| A path-scoped invariant always enforced | **rule** | `.claude/rules/X.md` |
| A deterministic guardrail that MUST trigger | **hook** | `.claude/settings.json` |

Decision rule: "must trigger every time" → hook; "invariant on files" → rule;
"reusable method" → skill; "delegated worker" → subagent.

## 3. Apply least privilege (subagents)
List the strict minimum of tools. Read/search only → `Read, Grep, Glob`.
Add `Write/Edit` only if it produces files, `Bash` only if it
executes. Justify each tool. Choose `model`: `sonnet` by default, `opus`
if high-level design/judgment is required.

## 4. Honor the frontmatter contract
- **Agent**: `name`, `description` (ends with "To be called for…"), `tools`, `model`;
  body "You are…" concise in French, closing "You return a synthesis: …".
- **Skill**: `name`, `description` (explicit trigger); body in numbered steps.

## 5. Check idempotence before writing
Does the file already exist? If it differs, **show a diff and ask** before
any modification. Otherwise, create it.

## 6. Test discovery
Confirm the mechanism is properly picked up (the agent/skill appears in the list,
the hook triggers on a mock case, the rule matches the right path). No green
test → no delivery.

## 7. Register (protected zone → convergence)
Prepare the patch: a line in the §6 roster of the root `CLAUDE.md`, and if a new
owned module appears, a line in the partition table of `docs/parallel-ops.md`.
These **protected zone** files change ONLY via the convergence session:
prepare the patch, do not apply it from a peripheral worktree.

## 8. Synthesis
Return: mechanism + justification, tools + justification, files touched,
test result, registration patch to apply, risks.
