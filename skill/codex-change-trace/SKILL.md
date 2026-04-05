# Codex Change Trace Workflow

## Purpose
Automatically record completed AI task changes into a structured Markdown logging system so both human developers and future agents can understand:
- what changed
- what was implemented
- how debugging happened
- what the root cause was
- how the result differs from the original plan
- what risks or follow-up work remain

This workflow is append-only. It preserves history instead of rewriting it.

---

## When to Trigger
Trigger this workflow only at a completed task node.

A completed task node means:
- the implementation / fix / refactor / docs / test / chore task is finished
- there is a concrete result worth recording

Do **not** trigger during intermediate editing.

If one completed node contains multiple task types, split them into multiple records.

---

## Supported Task Types
Only use these task types:

- feature
- debug
- refactor
- docs
- test
- chore

Each task type must be written into its own log file under the matching subdirectory.

---

## Output Locations

### Main timeline index
Write and append to:

`docs/log-index.md`

### Detailed task logs
Write each task log to:

`docs/logs/{type}/`

Directory structure:

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

If these directories do not exist, create them automatically.

---

## File Naming Convention
Each detailed task log must use this format:

`YYMMDD-HHMM_{type}-{slug}-{task-id}.md`

Rules:
- `slug`: derived from the one-line task title
- use kebab-case
- maximum 6 words
- `task-id`: 8-character hexadecimal short hash

Example:

`260403-1430_feature-add-login-endpoint-a1b2c3d4.md`

If a filename conflicts, append `_` plus a random 3-digit number.

Example:

`260403-1430_feature-add-login-endpoint-a1b2c3d4_382.md`

---

## Required Inputs
Collect these from the finished task context:

- one-line task title
- task type
- completion time
- affected files
- diff summary
- implementation summary
- risk notes

Optional but important when available:
- debug process
- bug reason
- original plan
- plan source
- deviation from original plan
- related previous records
- follow-up suggestions

---

## Original Plan Rules
Treat something as the original plan only if it comes from:
- user-provided instructions
- written project/task documentation
- issue or task description

Do **not** treat agent self-generated planning as the original plan unless that plan has been explicitly written into documentation and can be referenced.

If the original plan cannot be confirmed, write exactly:

`原计划不清楚`

Do not guess.

---

## Write Rules
For every completed task record, write both:
1. one detailed log file
2. one appended entry in `docs/log-index.md`

Success requires both writes to succeed.

Do not modify old log files.
Do not overwrite previous records.
If supplementary information is needed later, create a new log file and link related old records.

---

## Detailed Log Template
Use the following Markdown structure:

```markdown
# 任务记录：{task_title}

## 任务摘要
{task_summary}

## 任务类型
{task_type}

## 完成时间
{completed_at}

## 相关文件
- {file_1}
- {file_2}

## Diff 摘要
{diff_summary}

## 实现内容
{implementation_summary}

## Debug 过程
{debug_process_or_empty}

## Bug 原因
{bug_reason_or_empty}

## 与原计划差异
- 原计划来源：{plan_source_or_原计划不清楚}
- 差异说明：{plan_deviation_or_无/原计划不清楚}

## 风险与后续建议
{risk_notes_and_follow_up}

## 关联记录
- {related_record_1}
- {related_record_2}
```

Fields like debug process and bug reason may be empty when not applicable, but the headings must still exist.

---

## Main Index Append Format
Append entries to `docs/log-index.md` using this structure:

```markdown
## {completed_at} | {task_type} | {task_title}

- 摘要：{task_summary}
- 详情：`docs/logs/{type}/{filename}`
- 受影响文件数：{file_count}
- 计划偏差：{yes_or_no_or_原计划不清楚}
- 关联记录：{related_records_or_none}
```

Always append in chronological order of execution.

---

## Multi-Type Task Rule
If one completed node contains multiple types, split them.

Examples:
- debug + feature => create two detailed logs and two index entries
- feature + test => create two detailed logs and two index entries
- refactor + docs => create two detailed logs and two index entries

Do not merge multiple task types into a single detailed log.

---

## Failure Handling
If writing fails:
- do not block the main task result
- emit a downgrade warning
- clearly identify whether failure happened in:
  - detailed log creation
  - main index append
  - both

If context is incomplete:
- write based on available information
- explicitly mark unclear fields
- add a warning in the current conversation output

---

## Acceptance Criteria
This workflow is complete only when:
- the detailed log file is successfully written
- `docs/log-index.md` is successfully appended
- the file is stored in the correct task-type directory
- the filename matches the required pattern
- required sections exist in the detailed log
- original plan handling follows the allowed-source rule
- no old record is modified
- multi-type tasks are split correctly

---

## Agent Behavior Priorities
Prioritize:
1. accuracy over completeness when context is unclear
2. explicit unknown markers over inference
3. append-only logging over editing history
4. type separation over convenience
5. human readability and future-agent handoff compatibility
