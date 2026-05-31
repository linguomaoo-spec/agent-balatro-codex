# 运行日志到策略记忆

## 目标

把 `runs/*.jsonl`、`runs/eval/` 和子 agent 分析结果提炼为可复查的策略记忆。
这里不保存完整日志，只保存摘要、证据路径和后续行动。

## 分析流程

1. 选定固定 seed、deck、stake 和 genome。
2. 运行评估脚本生成日志。
3. 使用 `python3 -m balatro_agent summarize-eval --log-dir runs/eval` 生成只读指标摘要。
4. 使用 `python3 -m balatro_agent build-replay --log-dir runs/eval --output strategy/runs/replay.jsonl` 抽取错误动作和终局案例。
5. 找出失败阶段、最后动作、被拒绝动作、错误详情和状态摘要。
6. 判断失败更像是手牌、商店、盲注、状态解析、动作合法性还是评估指标问题。
7. 把有证据的观察写入 `research/findings.md`。
8. 把可复用的策略写入 `strategy/` 对应阶段或主题文件。

## 子 agent 产出格式

```text
任务：
输入文件：
观察：
证据：
建议策略记忆更新：
仍需验证：
```

## 最小指标

- 胜负状态。
- 最高 ante。
- 步数。
- 失败阶段。
- 最后选中动作和实际执行动作。
- 错误动作和 BalatroBot 错误详情。
- 当前金钱、小丑牌数量和盲注要求。
- 分数差距和被拒绝动作数量。

## 固定 seed 分组

- `dev`：快速迭代和调试，默认入口。
- `regression`：检查旧 seed 是否退化。
- `heldout`：策略晋升前检查过拟合。

默认分组位于 `config/eval-seeds.json`。显式 `SEEDS="..."` 会覆盖 cohort。

## 策略晋升门槛

候选策略或 genome 先在 `dev` cohort 上验证收益，再在 `regression` 和 `heldout`
cohort 上检查退化。推荐流程：

1. 保存 baseline 摘要：`python3 -m balatro_agent summarize-eval --log-dir runs/eval-baseline > runs/baseline-summary.json`
2. 保存候选摘要：`python3 -m balatro_agent summarize-eval --log-dir runs/eval-candidate > runs/candidate-summary.json`
3. 比较门槛：`BASELINE=runs/baseline-summary.json CANDIDATE=runs/candidate-summary.json COHORT=regression sh scripts/promotion-gate.sh`

默认阻断条件：

- `max_ante` 下降。
- `win_rate` 下降。
- `error_count` 增加。
- baseline 中已经胜利的 seed 在候选中丢失胜利。
- `heldout` 中 `rejected_count` 增加。

被阻断的候选只能保留为工作假设或失败案例，不能晋升为稳定策略。

## replay 案例类型

- `error`：执行动作触发 BalatroBot 错误。
- `decision`：高分差、最后手牌或被拒动作相关的关键决策片段。
- `terminal_win`：终局胜利样本。
- `terminal_loss`：终局失败样本。
- `terminal_unknown`：终局但缺少明确 `won` 字段。

## replay 检索和子 agent 注入

构建 replay 后，可以查询相关案例：

```bash
python3 -m balatro_agent replay-query --replay strategy/runs/replay.jsonl --phase SHOP --limit 5
```

生成子 agent 任务包时可以注入相关案例：

```bash
REPLAY=strategy/runs/replay.jsonl PHASE=SHOP REPLAY_LIMIT=5 \
  sh scripts/subagent-task.sh "分析最近商店失败"
```

子 agent 应基于这些案例提出可验证的策略假设，并在输出中说明证据路径。
