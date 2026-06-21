# 禁止预设 Seed 启动设计

日期：2026-06-21
目标：禁止通过交互式启动入口以预设 seed 开始 Balatro 游戏，同时保留用于离线评估的固定 seed 流程。

## 范围

- `scripts/start.sh` 不再接受 `SEED` 环境变量：检测到非空值即退出，并给出明确错误。
- CLI 的 `start` 子命令不再接受 `--seed`：提供该参数即返回参数错误，且不请求 BalatroBot。
- `eval`、`evolve`、seed cohort 配置和 checkpoint 回放不在本次修改范围内。

## 设计

脚本入口在调用 Python CLI 前检查 `SEED`。这能阻止文档、shell 历史记录或环境配置意外复用预设局。

CLI 保留 `--seed` 参数以兼容解析器的错误提示路径，但在执行 `start` 前拒绝它。这个边界覆盖直接调用 `python3 -m balatro_agent start --seed ...` 的情况，又不会影响评估器内部调用 `BalatroBotClient.start(..., seed=...)`。

## 错误行为

- `SEED=AGENT1 sh scripts/start.sh`：非零退出，错误信息说明实际启动禁止预设 seed。
- `python3 -m balatro_agent start --seed AGENT1`：抛出清晰的参数错误，且不发送 `start` RPC。
- 未传 seed 的两种启动方式保持原有 deck/stake 行为。

## 验证

- 增加 CLI 单元测试，确认有 `--seed` 时会拒绝且 client 未调用。
- 增加脚本级测试或等价 shell 检查，确认 `SEED` 被拒绝。
- 运行相关 CLI 测试及完整单元测试套件。
