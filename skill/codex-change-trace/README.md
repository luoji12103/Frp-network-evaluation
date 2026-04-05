# Codex Change Trace Workflow

一个面向 Codex 的任务日志 Skill，用于在任务完成节点自动将 AI 改动沉淀为结构化 Markdown 记录。

## 目标
把以下信息稳定沉淀到统一目录：
- 改动内容
- 实现功能
- debug 过程
- bug 原因
- 与原计划的偏差
- 风险与后续建议
- 关联记录

## 适用对象
- 人类开发者复盘
- 下一位接手的 agent
- 需要保留清晰时间线的仓库

## 目录规范
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

## 核心规则
1. 只在“任务完成节点”记录，不在中间编辑阶段记录。
2. 若一个完成节点中包含多个类型子任务，必须拆分成多份详情文档。
3. 主线索引 `docs/log-index.md` 与详情文档必须双写成功。
4. 不允许改写已有记录；补充信息必须新建文档并关联旧记录。
5. 原计划只能来自：
   - 用户提供
   - 已写入文档的计划
   - issue / task 描述
6. 无法确认原计划时，必须写：`原计划不清楚`

## 文件命名
详情文档统一使用：

`YYMMDD-HHMM_{type}-{slug}-{task-id}.md`

其中：
- `slug`：由一句话标题转成 kebab-case，最长 6 个词
- `task-id`：8 位十六进制短 hash

## 包含内容
- `SKILL.md`：最终技能定义
- `README.md`：中文说明
- `README.en.md`：英文说明
- `templates/`：初始化与日志模板
- `examples/`：示例目录与示例日志

## 推荐接入方式
把本目录放入你的技能仓库后，让 Codex 在每个任务完成节点执行本 Skill。
