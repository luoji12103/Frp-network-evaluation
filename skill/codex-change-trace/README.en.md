# Codex Change Trace Workflow

A Codex-oriented workflow for automatically writing structured Markdown task logs at task completion boundaries.

## Goal
Persist the following information into a stable, searchable log structure:
- what changed
- what was implemented
- debugging process
- bug root cause
- deviation from the original plan
- risks and follow-up actions
- related records

## Intended readers
- human developers
- the next handoff agent
- repositories that need a clear execution timeline

## Directory convention
```text
docs/
  log-index.md
  logs/
    feature/
    debug/
    refactor/
    docs/
    test/
    chore/
```

## Core rules
1. Log only at a completed task node, never during intermediate edits.
2. If one completed node contains multiple task types, split them into multiple detailed logs.
3. Both the main index and the detailed log must be written for success.
4. Do not rewrite existing records. Add a new supplementary record and link the older one when needed.
5. An original plan is valid only when it comes from:
   - user instructions
   - documented plans
   - issue / task descriptions
6. If the original plan cannot be confirmed, write exactly: `原计划不清楚`

## Detailed log naming
Use:

`YYMMDD-HHMM_{type}-{slug}-{task-id}.md`

Where:
- `slug` = kebab-case from the one-line task title, max 6 words
- `task-id` = 8-character hexadecimal short hash

## Package contents
- `SKILL.md`: final skill definition
- `README.md`: Chinese guide
- `README.en.md`: English guide
- `templates/`: bootstrap and log templates
- `examples/`: sample directories and sample logs
