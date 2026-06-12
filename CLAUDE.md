# CLAUDE.md

## 项目目标

打造尽可能强的小丑牌（Balatro）求解器：通过可重复评估、策略记忆、周期性研究，持续提升自动化 agent 的策略质量、通关稳定性和得分能力。长期目标：通关所有难度。

## 技术概要

- Python 包名：`balatro_agent`
- Python 3.9+，无运行时依赖
- 测试命令：`python3 -m unittest discover -s tests`
- 策略入口：`strategy/index.md`
- 研究入口：`research/`
- BalatroBot 本地地址：`http://127.0.0.1:12346`
- 启动游戏：`sh "/Users/suriness/Library/Application Support/Steam/steamapps/common/Balatro/run_lovely_macos.sh"`
- 访问 BalatroBot 需绕过本地代理：`NO_PROXY=127.0.0.1,localhost`

## 每次研究运行前必须阅读

1. `CLAUDE.md`
2. `README.md`
3. `research/memory.md` — 项目记忆（稳定事实、工作假设、未知项）
4. `research/findings.md` — 有证据支撑的发现
5. `research/decisions.md` — 影响后续工作的决策
6. `research/questions.md` — 待解决问题
7. `research/runs/` 中最近运行日志

## 研究运行流程

1. 说明本次运行目标和重要假设
2. 从 `research/questions.md` 识别高优先级问题
3. 添加新发现前先检查已有发现（去重）
4. 优先从一手来源收集证据（代码、日志、测试）
5. 用简洁且有来源支撑的内容更新对应研究文件
6. 创建或更新当天运行日志：`research/runs/YYYY-MM-DD.md`
7. 如果运行失败或未通关：基于日志总结失败原因，说明证据来源
8. 如果失败原因、策略理解或假设发生变化：更新 `research/memory.md`
9. 给下一轮运行明确的成功率估计（百分比或区间）
10. 每轮结束创建 git commit，只提交本轮产生的文件

## 记忆更新规则

- 仅当项目目标、稳定事实、工作假设或重要未知项发生实质变化时才更新 `research/memory.md`
- 记忆要简洁，总结持久项目状态，不复制每次运行日志
- 除非有新证据明确取代旧结论，保留历史结论
- 替换或修订结论时记录原因，指向新证据或决策
- 每次修改记忆时更新 `Last updated` 字段

## 证据规则

- 优先一手来源：仓库代码、测试、日志、官方文档、直接观察行为
- 二手来源只用于背景或线索，需在其他地方确认
- 在 `research/sources.md` 记录长期有效的来源位置
- 在 `research/findings.md` 记录具体证据，细节足够复查
- 包含来源名称、路径或 URL；对网络来源记录访问日期；标注置信度
- 不把无引用来源的主张当作稳定事实

## 信息分类

- **稳定事实**：有充分证据支持、预计在项目或上游变化前保持成立的陈述 → `research/memory.md`
- **工作假设**：对下次运行有用但仍需验证的判断 → `research/memory.md`
- **开放问题**：需要调查或决策的未知项 → `research/questions.md`
- **新发现**：本次运行得到的有证据支撑的观察 → `research/findings.md`
- **决策**：影响后续工作的方向或约束 → `research/decisions.md`

## 去重与历史保留

- 添加发现前搜索已有条目，确认不重复
- 已存在的主张只有补充了有意义的新证据/置信度/影响时才更新
- 不要用不同措辞重复同一发现
- 不要仅因发现或决策过时就删除旧记录
- 过时决策标注 `Superseded by`，新增更新后的决策
- 新发现改变旧发现解释时，保留两者并说明关系

## 每次运行后的固定输出格式

```
运行总结：
- 目标：
- 已阅读文件：
- 已采取行动：
- 新发现：
- 失败原因：
- 记忆更新：
- 决策更新：
- 开放问题：
- 下次成功率估计：
- 建议的下一次运行：
- 变更文件：
- Commit：
```

如果某个类别没有变化，写 `无`。

## 常用命令

```bash
# 检查 BalatroBot 健康
NO_PROXY=127.0.0.1,localhost python3 -m balatro_agent --timeout 3 doctor

# 运行固定 seed 评估（dev cohort）
NO_PROXY=127.0.0.1,localhost python3 -m balatro_agent --timeout 15 eval \
  --seeds AGENT1 AGENT2 AGENT3 --max-steps 500 --log-dir runs/eval/live-YYYYMMDD-HHMMSS

# 评估汇总
python3 -m balatro_agent summarize-eval --log-dir runs/eval/<dir>

# 查看游戏状态
NO_PROXY=127.0.0.1,localhost python3 -m balatro_agent --timeout 3 gamestate

# 运行测试
python3 -m unittest discover -s tests
```
