# 价值函数驱动的适应度评估 · 设计文档

日期：2026-06-02
状态：设计阶段
关联：[[strategy/index]], [[research/memory]]

## 1. 问题陈述

当前进化系统的 `EvalResult.score()` 使用手工加权的标量适应度函数：

```python
fitness = 100×win + 20×ante + 0.02×steps + 0.002×score + 0.05×money + 1.5×jokers
```

**四个核心问题**：

1. **数量级耦合**：各维度系数手工压平到相近数量级。游戏版本或 deck/stake 变化会导致公式失效。
2. **单一标量损失信息**：两个 genome 可能 fitness 相同但优势维度完全不同，标量无法区分。
3. **只看终点不看过程**：一个 ante 1-3 完美但 ante 4 崩盘的 genome，和一个全程平庸但走到 ante 5 的 genome，后者被高估。
4. **不利用决策日志**：JSONL 中每个动作的候选列表、拒绝原因、fallback 频率等信号被完全丢弃。

**目标**：设计一个能从游戏状态预测最终结果的 **价值函数 V(state)**，替代手工加权作为进化适应度。

## 2. 方案概述

### 2.1 核心思路

```
V(state) = E[ 最终 ante | 当前处于 state ]
fitness(genome) = mean( V(s) for s in run.states )
```

训练一个监督学习模型，输入 GameState 特征，输出预测的最终 ante。用这个模型的预测值作为进化适应度。

### 2.2 关键优势

- **不需要手工调系数**：模型从数据中自动学习各特征的相对重要性。
- **利用过程信息**：每一步状态都产生一个 V 预测，聚合后反映整局质量。
- **随数据变强**：数据越多，V 越准，进化选择越有效。形成正向飞轮。
- **可解释**：XGBoost 输出特征重要性排名，直接告诉你哪些因素最重要。

### 2.3 为什么先做路线 4（价值函数）而不是其他路线

| 路线 | 定位 |
|---|---|
| 路线 2（分阶段加权）| 仍然需要手工设计系数，只是更细粒度。可作为 V 的 baseline 对照。|
| 路线 3（决策质量反馈）| 信号来自 agent 自身行为（fallback 次数等），可能和真实游戏质量不相关。适合作为 V 的辅助特征。|
| **路线 4（价值函数）**| 直接逼近真实期望，从根本上解决手工加权问题。|

路线 2 和 3 可以作为路线 4 的特征输入或验证对照，不是替代关系。

## 3. 特征工程

### 3.1 特征分类

从 `GameState.summary()` 和原始 JSON 中提取约 80 个特征：

#### 数值特征（约 25 维）

| 特征 | 来源 | 说明 |
|---|---|---|
| ante | state.ante | 当前 ante 层数 (1-8) |
| round_number | state.round_number | 累计回合数 |
| money | state.money | 当前现金 |
| hands_remaining | state.hands_remaining | 剩余出牌次数 |
| discards_remaining | state.discards_remaining | 剩余弃牌次数 |
| score | state.score | 当前筹码得分 |
| required_score | state.blind_requirement | 盲注目标分 |
| score_ratio | score / required_score | 完成比例 |
| joker_count | len(state.jokers) | 持有小丑牌数 |
| consumable_count | len(state.consumables) | 持有消耗品数 |
| joker_slots | state.joker_limit | 小丑牌槽位上限 |
| consumable_slots | state.consumable_limit | 消耗品槽位上限 |
| joker_slots_free | joker_limit - joker_count | 空余小丑槽 |
| hand_size | len(state.hand) | 当前手牌数 |
| deck_cards_remaining | raw.deck/cards count | 牌组剩余张数 |
| money_per_round | money / max(1, round_number) | 金钱效率 |
| hands_used | initial_hands - hands_remaining | 已用手数 |
| discards_used | initial_discards - discards_remaining | 已用弃牌数 |
| hand_level_avg | raw.hands 各牌型等级均值 | 牌型平均等级 |
| hand_level_max | raw.hands 各牌型等级最大值 | 最高牌型等级 |
| voucher_count | raw.vouchers 数量 | 持有优惠券数 |
| reroll_cost | raw.shop 重掷成本 | 商店重掷价格 |

#### 类别特征（约 6 维，需 one-hot 或 embedding）

| 特征 | 取值 | 编码方式 |
|---|---|---|
| deck | RED, BLUE, YELLOW, GREEN, BLACK, ... | One-hot (~10d) |
| stake | WHITE, RED, GREEN, BLACK, ... | One-hot (~9d) |
| phase | BLIND_SELECT, SELECTING_HAND, SHOP, ... | One-hot (~6d) |
| boss_blind_type | raw.blinds.current 的盲注类型 | One-hot (~10d) |

#### Joker 编码（约 20 维）

**方案 C（推荐）**：已知强 Joker 多热编码 + 手工协同特征。

- 多热编码：对 strategy/jokers/ 中记录的已知重要 Joker（约 30-40 个），每个一位 binary indicator。
- 协同对特征（10 维 binary）：has_photo_chad（Photograph+Hanging Chad）、has_scholar_half（Scholar+Half Joker）等。
- 聚合特征：scaling_joker_count、xmult_count、chip_joker_count、econ_joker_count。

#### 交叉特征（约 10 维）

| 特征 | 计算方式 |
|---|---|
| total_score_potential | score + hands_remaining × avg_hand_score × avg_mult |
| money_pressure | money < cash_reserve ? 1 : 0 |
| shop_value_density | shop_cards 中 joker 平均价值 / 平均价格 |
| score_gap_ratio | (required_score - score) / (hands_remaining × avg_hand_score) |
| joker_synergy_pairs | 已知协同对在持有 joker 和商店 joker 之间的匹配数 |
| shop_quality | shop_cards 中评分 > 20 的 joker 数量 |

### 3.2 特征提取模块

新增 `balatro_agent/features.py`：

```python
def extract_features(state: GameState) -> Dict[str, float]:
    """从 GameState 提取 ~80 维特征向量"""
    ...

def extract_from_jsonl_record(record: dict) -> Dict[str, float]:
    """从 JSONL 决策日志的一行中提取特征（用于训练）"""
    ...

def features_to_array(feats: Dict[str, float], 
                       categorical_encoders: dict) -> np.ndarray:
    """特征字典 → numpy 数组，处理类别编码"""
    ...
```

## 4. 模型架构

### 4.1 三阶段演进路线

```
阶段 1 (数据 < 10K)    阶段 2 (10K-100K)       阶段 3 (> 100K)
┌──────────────┐      ┌──────────────┐       ┌──────────────┐
│   XGBoost    │ ──→  │   小型 MLP    │  ──→  │  Transformer │
│              │      │              │       │              │
│ 80 手工特征   │      │ Joker Emb(16)│       │ Joker tokens │
│ 回归 final_  │      │ + 数值特征    │       │ + 手牌序列   │
│ ante         │      │ 多任务输出    │       │ Self-Attn    │
│ 特征重要性    │      │              │       │              │
└──────────────┘      └──────────────┘       └──────────────┘
```

### 4.2 阶段 1 详情：XGBoost 基线

**输出**：单目标回归 `final_ante`（1-8）。后续阶段可扩展为多目标。

**超参数**：

| 参数 | 值 | 说明 |
|---|---|---|
| objective | reg:squarederror | MSE 回归 |
| max_depth | 4 | 从小开始，防止过拟合 |
| learning_rate | 0.05 | 保守学习率 |
| n_estimators | 500 + early_stopping_rounds=20 | 自动早停 |
| subsample | 0.8 | 行采样 |
| colsample_bytree | 0.7 | 列采样 |
| min_child_weight | 5 | 正则化 |
| reg_lambda | 1.0 | L2 正则化 |

**代码依赖**：`xgboost`（唯一新增的运行时依赖）。

### 4.3 阶段 2 展望：小型 MLP

当数据量 > 10K run-steps 后，切换为 MLP：

- Joker Embedding：约 150 种 Joker × d=16 的嵌入矩阵
- 数值特征直接拼接
- 2-3 层全连接 [128, 64, 32]，ReLU + Dropout(0.2)
- 多任务输出：ante 回归 + win 分类 + score 对数回归
- 使用不确定性加权自动平衡多任务损失

### 4.4 阶段 3 展望：Transformer

数据充足时（> 100K），将 Joker 序列和手牌序列作为 token 输入 self-attention，自动建模卡片之间的交互关系。

## 5. 训练方法

### 5.1 标签构造（Monte Carlo 回报）

```
对于每次完成的 run：
  final_ante = run.final_state.ante  # 标签
  final_score = run.final_state.score
  win = run.final_state.won

  对于 run 中的每一步 step：
    X = extract_features(step.state)
    Y = final_ante  # 同一次 run 的所有 step 共享标签
    dataset.append((X, Y))
```

### 5.2 验证策略

**必须使用 Run-Level Split**：同一次 run 的所有步骤必须在同一个 split 中。这是最关键的防泄漏措施。

```
训练集：80% 的 run（按 run_id 分组，所有步骤）
验证集：10% 的 run
测试集：10% 的 run
```

**Stratification 层级**（按优先级）：
1. 按 `final_ante` 分层（确保每个 ante 段都有）
2. 按 `deck` 分层
3. 按时间分层（老数据训练，新数据验证 — 最接近真实使用场景）

### 5.3 损失函数（阶段 1）

单目标简化版：

```python
loss = MAE(predicted_ante, actual_ante)
```

MAE 比 MSE 更直观（"平均差几个 ante"），且对离群值不敏感。

### 5.4 防过拟合策略

| 层面 | 措施 |
|---|---|
| 数据 | Run-level split；每 run 采样 ≤ 20 步；通关 run 过采样 3× |
| 模型 | 小 max_depth；L1+L2 正则化；early stopping |
| 评估 | heldout seed cohort 最终检验；监控残差 by ante |
| 持续 | 检测新数据分布偏移（top-5 特征均值偏离 > 1σ → 触发重训）|

### 5.5 评估指标

| 指标 | 计算 | 目标 |
|---|---|---|
| Ante MAE | |pred - actual| | < 1.0 ante |
| Rank Correlation | Spearman ρ(predicted, actual) | > 0.7 |
| Top-K Recall | 预测最高的 K 个 run 中，真实最高 ante 的比例 | Top-3 > 80% |
| 残差 by Ante | 每个 ante 段单独的 MAE | 高 ante 段不显著恶化 |

### 5.6 持续训练循环

```
进化产生新 JSONL
  → 增量加入训练集
  → 检查分布偏移（新 run 特征分布 vs 训练集）
  → 满足触发条件：重训模型
  → 新模型替换旧模型
  → 下一轮进化用新模型
```

**触发条件**（满足任一）：
1. 新增 run 数 > 训练集 run 数的 20%
2. 新 run 在 top-5 特征上的分布均值偏离训练集 > 1 标准差
3. 手动触发

## 6. 与进化系统集成

### 6.1 修改 EvalResult.score()

```python
# 当前（evolution.py）
@property
def score(self) -> float:
    scores = []
    for run in self.runs:
        scores.append(
            status_bonus + ante * 20.0 + steps * 0.02 
            + final_score * 0.002 + money * 0.05 + jokers * 1.5
        )
    return statistics.mean(scores)

# 新版本
@property
def score(self) -> float:
    if self._model is None:
        return self._heuristic_score()  # fallback
    values = []
    for run in self.runs:
        run_values = [self._model.predict(s) for s in run.states]
        values.append(statistics.mean(run_values))
    return statistics.mean(values)
```

### 6.2 EvalResult 增加日志字段

```python
def as_dict(self) -> Dict[str, Any]:
    return {
        "score": self.score,
        "score_type": "model" if self._model else "heuristic",  # 新增
        "model_version": self._model_version,                    # 新增
        "model_mean_value": ...,                                 # 新增
        "genome": ...,
        "runs": ...,
    }
```

### 6.3 冷启动方案

```
Step 0: 用现有启发式 fitness 跑首批数据
  → 随机变异 N 个 genome × M 个 seed
  → 收集 JSONL + 终局统计

Step 1: 训练 V₁
  → XGBoost 在首批数据上训练
  → 评估 MAE、Rank Corr、Top-K Recall
  → 确认 Val MAE < 1.0 ante

Step 2: 启动进化
  → EvolutionEngine 使用 V₁ 做 fitness
  → 每代产生新数据

Step 3: 持续迭代
  → 数据积累 → 重训 V₂, V₃, ...
  → 观察 fitness 排序是否更稳定
  → heldout seed 通关率是否提升
```

### 6.4 兼容性

- `EvolutionEngine` 接受可选的 `model` 参数，为 None 时自动退化为启发式 fitness。
- `make_live_run_factory` 无需改动——Runner 不知道也不关心 fitness 怎么算。
- 现有 `scores.json` 格式向后兼容，新增字段不影响已有工具。

## 7. 数据现状与可行性

### 7.1 已有数据

| 来源 | 路径 | 规模 |
|---|---|---|
| 评估日志 | runs/eval/**/*.jsonl | ~15-20 个 run |
| 进化日志 | runs/evolution/**/*.jsonl | ~15 个 run |
| 人类游玩 | runs/human/*.jsonl | 2 个 session |
| **合计估算** | | **~30-40 个 run × 平均 60 step = ~2000 条** |

### 7.2 可行性判断

- **2000 条 × 80 特征**：对 XGBoost 来说样本偏少但可尝试。特征维度不算高。
- **Run 数量 (~35)**：Run-level split 下 train/val/test 分别只有 ~28/3/4 个 run。验证集太小，统计意义有限。
- **数据多样性**：大部分 run 死在 ante 1-5，高 ante 和通关数据极少。

**结论**：技术上可行，但需要**主动生成更多数据**。建议在实现特征提取后，先用随机 genome 变体 + 多 seed 跑 100-200 个 run 扩充训练集。

## 8. 实现计划

### 8.1 文件变更

| 文件 | 操作 | 说明 |
|---|---|---|
| balatro_agent/features.py | **新建** | 特征提取模块 |
| balatro_agent/value_model.py | **新建** | XGBoost 模型训练/推理封装 |
| balatro_agent/evolution.py | **修改** | EvalResult.score() 支持 model 模式 |
| balatro_agent/cli.py | **修改** | 新增 train-model / eval-model 子命令 |
| scripts/train-value-model.sh | **新建** | 训练流程脚本 |
| tests/test_features.py | **新建** | 特征提取测试 |
| tests/test_value_model.py | **新建** | 模型测试 |
| pyproject.toml | **修改** | 新增 xgboost 依赖 |

### 8.2 步骤

| 步骤 | 产出 | 预计工时 |
|---|---|---|
| 1. 特征提取器 | `features.py` + 测试，能从 GameState/JSONL 提取 ~80 维特征 | 2-3h |
| 2. 数据管道 | 扫描 runs/ 生成训练集，支持 run-level split 和增量更新 | 1-2h |
| 3. XGBoost 训练 | 训练脚本 + 评估报告（MAE, Rank Corr, 特征重要性）| 2-3h |
| 4. 集成 EvalResult | 可选切换 model/heuristic 模式，向后兼容 | 1h |
| 5. 回归验证 | 在 dev cohort 上对比新旧 fitness 的排序一致性和通关率 | 1-2h |
| 6. 数据扩充 | 用随机 genome 跑 100+ run 扩充训练集 | 视 BalatroBot 速度 |
| **MVP 总计** | | **约 8-12h** |

### 8.3 MVP 验收标准

1. XGBoost 模型在验证集上 **MAE < 1.0 ante**
2. **Spearman ρ > 0.7**（模型排序和真实排序基本一致）
3. 使用模型 fitness 的进化 **至少不差于** 启发式 fitness（在 dev cohort 上 ante 深度不退化）
4. 所有现有测试通过
5. 训练/评估流程可一键运行

## 9. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 数据不足 | 模型欠拟合，预测不准 | 主动生成：随机 genome × 多 seed 批量跑 |
| 分布偏移 | 新 genome 行为超出训练分布，V 预测失准 | 监控特征偏移，超阈值自动重训 |
| 奖励黑客 | Genome 学会利用 V 盲区，而非真正变强 | heldout seed 最终检验；定期人工抽查 |
| 终局稀疏 | ante 7-8 数据极少，V 对后期预测不可靠 | 对人类高手 replay 加权采样；课程学习 |
| xgboost 依赖 | 纯 Python 项目的第一个外部依赖 | xgboost 是成熟库，pip 安装无额外系统依赖 |

## 10. 后续演进方向

1. **路线 2+3 作为 V 的特征输入**：分阶段 checkpoint 数据（每过一个 ante 的状态快照）和决策质量信号（fallback 率、候选覆盖度）都可以作为 V 的输入特征，增强预测能力。

2. **主动探索**：当 V 对某些状态区域置信度低时，引导进化去探索那些区域，类似 Bayesian Optimization 的 acquisition function。

3. **V 用于实时决策**：Agent 做决策时，用 `V(next_state) - V(current_state)` 作为动作的 advantage 估计，替代当前的手工打分。

4. **离线 replay 分析**：用 V 回溯历史日志，识别"明明状态很好却输了"的 run，分析失败原因。

---

**关联文档**：[[strategy/index]], [[research/memory]], [[research/questions]], [[research/decisions]]
