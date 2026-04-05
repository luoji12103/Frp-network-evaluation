# Integration Guide

## Recommended repository placement
Put this package into a skills directory such as:

```text
skills/codex-change-trace/
```

## Runtime expectations
At task completion, the agent should:
1. detect task completion
2. classify task type(s)
3. collect changed files and diff summary
4. validate whether an original plan exists
5. write one or more detailed task logs
6. append matching entries to `docs/log-index.md`

## Append-only guarantee
This workflow assumes:
- existing log files are immutable
- future corrections are represented by a new supplementary log
- related logs are linked through the `关联记录` section

## Suggested repository bootstrap
Copy `templates/initial-log-index.md` to:

```text
docs/log-index.md
```

And ensure these directories exist:

```text
docs/logs/feature
docs/logs/debug
docs/logs/refactor
docs/logs/docs
docs/logs/test
docs/logs/chore
```

## Notes for mixed task types
If one completion boundary includes multiple types:
- do not merge them
- generate one file per type
- create one index entry per file

## Suggested unknown markers
Use these exact markers where needed:
- `原计划不清楚`
- `无`
- `待后续补充`
