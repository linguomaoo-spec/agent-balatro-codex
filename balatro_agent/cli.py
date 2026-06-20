from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import List, Optional

from balatro_agent.analysis import (
    compare_eval_summaries,
    load_replay_cases,
    query_replay_cases,
    summarize_jsonl_logs,
    write_replay_cases,
)
from balatro_agent.auto_evolution import AutoEvolution, AutoEvolutionConfig
from balatro_agent.client import DEFAULT_BASE_URL, BalatroBotClient
from balatro_agent.evolution import (
    EvolutionEngine,
    make_checkpoint_run_factory,
    make_live_run_factory,
)
from balatro_agent.elite import EliteArchive
from balatro_agent.model import Genome
from balatro_agent.orchestrator import DefaultOrchestrator
from balatro_agent.recorder import ActionRecorder, StateRecorder
from balatro_agent.runner import Runner
from balatro_agent.search import CheckpointScenarioLibrary, CheckpointSearchPlanner, SearchConfig
from balatro_agent.seeds import DEFAULT_SEEDS, load_seed_config, resolve_seed_list


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="balatro-agent",
        description="通过 BalatroBot 运行、评估和进化 Balatro 自动化 agent。",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="BalatroBot JSON-RPC 地址")
    parser.add_argument("--timeout", type=float, default=10.0, help="请求超时时间（秒）")
    parser.add_argument("--genome", type=Path, default=None, help="可选的 genome JSON 路径")
    parser.add_argument("--elite-archive", type=Path, default=None, help="可选的 per-seed elite 档案 JSON")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="检查 BalatroBot 健康状态")

    start = subparsers.add_parser("start", help="通过 BalatroBot 开始一局")
    start.add_argument("--deck", default="RED", help="牌组常量，例如 RED")
    start.add_argument("--stake", default="WHITE", help="赌注常量，例如 WHITE")
    start.add_argument("--seed", default=None, help="可选固定 seed")

    step = subparsers.add_parser("step", help="读取一次状态并执行一次决策")
    step.add_argument("--log", type=Path, default=Path("runs/decisions.jsonl"), help="决策日志路径")

    run = subparsers.add_parser("run", help="运行自动游戏循环")
    run.add_argument("--max-steps", type=int, default=500, help="最大执行步数")
    run.add_argument("--sleep", type=float, default=0.05, help="每步之间的等待秒数")
    run.add_argument("--log", type=Path, default=Path("runs/decisions.jsonl"), help="决策日志路径")
    run.add_argument("--seed", default=None, help="当前运行的固定 seed，用于读取 elite 先验")
    _add_search_arguments(run)

    record = subparsers.add_parser("record", help="只读记录人类游玩时的 BalatroBot 状态变化")
    record.add_argument("--output", type=Path, default=Path("runs/human/record.jsonl"), help="输出 JSONL 路径")
    record.add_argument("--interval", type=float, default=1.0, help="轮询间隔秒数")
    record.add_argument("--max-polls", type=int, default=None, help="最多轮询次数；默认一直运行")
    record.add_argument("--max-snapshots", type=int, default=None, help="最多写入的状态快照数；默认不限")
    record.add_argument("--record-unchanged", action="store_true", help="记录每次轮询，而不只记录状态变化")
    record.add_argument("--summary-only", action="store_true", help="只写状态摘要，不写原始 BalatroBot 状态")
    record.add_argument("--no-stop-on-game-over", action="store_true", help="遇到 GAME_OVER 后继续记录")

    record_actions = subparsers.add_parser("record-actions", help="只读记录人类游玩的决策动作到单个 JSON")
    record_actions.add_argument("--output", type=Path, default=Path("runs/human/actions.json"), help="输出 JSON 路径")
    record_actions.add_argument("--interval", type=float, default=1.0, help="轮询间隔秒数")
    record_actions.add_argument("--max-polls", type=int, default=None, help="最多轮询次数；默认一直运行")
    record_actions.add_argument("--no-stop-on-game-over", action="store_true", help="遇到 GAME_OVER 后继续记录")

    eval_cmd = subparsers.add_parser("eval", help="在多个 seed 上评估一个 genome")
    eval_cmd.add_argument("--deck", default="RED", help="牌组常量，例如 RED")
    eval_cmd.add_argument("--stake", default="WHITE", help="赌注常量，例如 WHITE")
    eval_cmd.add_argument("--seeds", nargs="*", default=None, help="评估用 seed 列表")
    eval_cmd.add_argument("--seed-config", type=Path, default=None, help="seed cohort 配置文件")
    eval_cmd.add_argument("--cohort", default="dev", help="从 seed 配置中选择的 cohort")
    eval_cmd.add_argument("--max-steps", type=int, default=500, help="每个 seed 的最大步数")
    eval_cmd.add_argument("--log-dir", type=Path, default=Path("runs/eval"), help="评估日志目录")
    _add_search_arguments(eval_cmd)

    summarize = subparsers.add_parser("summarize-eval", help="汇总 JSONL 评估日志")
    summarize.add_argument("--log-dir", type=Path, default=Path("runs/eval"), help="评估日志目录或单个 JSONL 文件")

    promotion_gate = subparsers.add_parser("promotion-gate", help="比较 baseline 和候选评估摘要，输出策略晋升判断")
    promotion_gate.add_argument("--baseline", type=Path, required=True, help="baseline summarize-eval JSON 文件")
    promotion_gate.add_argument("--candidate", type=Path, required=True, help="候选 summarize-eval JSON 文件")
    promotion_gate.add_argument("--cohort", default="dev", help="用于解释门槛的 cohort 名称")

    replay = subparsers.add_parser("build-replay", help="从 JSONL 评估日志抽取 replay 经验案例")
    replay.add_argument("--log-dir", type=Path, default=Path("runs/eval"), help="评估日志目录或单个 JSONL 文件")
    replay.add_argument("--output", type=Path, default=Path("strategy/runs/replay.jsonl"), help="输出 replay JSONL 路径")
    replay.add_argument("--limit", type=int, default=100, help="最多抽取的案例数量")

    replay_query = subparsers.add_parser("replay-query", help="从 replay JSONL 查询最相关案例")
    replay_query.add_argument("--replay", type=Path, default=Path("strategy/runs/replay.jsonl"), help="replay JSONL 路径")
    replay_query.add_argument("--phase", default=None, help="可选阶段过滤，例如 SHOP")
    replay_query.add_argument("--case-type", default=None, help="可选案例类型过滤，例如 error")
    replay_query.add_argument("--limit", type=int, default=5, help="返回案例数量")

    seed_cohorts = subparsers.add_parser("seed-cohorts", help="显示固定 seed cohort 配置")
    seed_cohorts.add_argument("--seed-config", type=Path, default=Path("config/eval-seeds.json"), help="seed cohort 配置文件")

    evolve = subparsers.add_parser("evolve", help="变异策略权重并保留最佳结果")
    evolve.add_argument("--deck", default="RED", help="牌组常量，例如 RED")
    evolve.add_argument("--stake", default="WHITE", help="赌注常量，例如 WHITE")
    evolve.add_argument("--seeds", nargs="*", default=None, help="评估用 seed 列表")
    evolve.add_argument(
        "--seed-config",
        type=Path,
        default=Path("config/eval-seeds.json"),
        help="seed cohort 配置文件",
    )
    evolve.add_argument("--cohort", default="dev", help="从 seed 配置中选择的 cohort")
    evolve.add_argument("--generations", type=int, default=3, help="进化代数")
    evolve.add_argument("--population", type=int, default=8, help="每代候选数量")
    evolve.add_argument("--max-steps", type=int, default=500, help="每个 seed 的最大步数")
    evolve.add_argument("--output-dir", type=Path, default=Path("runs/evolution"), help="进化输出目录")
    evolve.add_argument("--random-seed", type=int, default=1, help="进化随机数 seed")
    evolve.add_argument("--sim", action="store_true", help="使用历史场景的 scoring_sim 运行进化，不连接 BalatroBot")
    evolve.add_argument("--sim-log-dir", type=Path, default=None, help="--sim 的历史 JSONL 场景目录")
    _add_search_arguments(evolve)

    auto_evolve = subparsers.add_parser("auto-evolve", help="在当前分支自动修改、评估并晋升或回滚候选")
    auto_evolve.add_argument("--root", type=Path, default=Path("."), help="Git 仓库根目录")
    auto_evolve.add_argument("--mutator-command", required=True, help="可任意修改仓库的外部命令")
    auto_evolve.add_argument("--evaluator", type=Path, required=True, help="评估器：接收 COHORT 与 LOG_DIR 两个参数")
    auto_evolve.add_argument("--test-command", default="python3 -m unittest discover -s tests", help="候选测试命令")
    auto_evolve.add_argument("--run-root", type=Path, default=Path("runs/auto-evolve"), help="评估产物目录")
    auto_evolve.add_argument(
        "--baseline-eval-dir",
        action="append",
        dest="baseline_eval_dirs",
        type=Path,
        default=None,
        help="可重复：用于估计噪声的 baseline 评估目录。提供后 dev cohort 用 effect-size 分布判断晋升",
    )
    auto_evolve.add_argument("--effect-threshold", type=float, default=2.0, help="晋升所需 effect size（均值差/噪声σ）")
    auto_evolve.add_argument("--min-samples", type=int, default=2, help="baseline 每 seed 最小样本数，不足则保守拒绝")

    measure = subparsers.add_parser("measure", help="聚合多次 eval 目录的同 seed 分数分布，量化评估噪声")
    measure.add_argument("eval_dirs", nargs="+", type=Path, help="eval 日志目录列表")

    genome = subparsers.add_parser("write-default-genome", help="写入默认 genome JSON")
    genome.add_argument("path", type=Path, help="输出路径")

    return parser


def _add_search_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--search", action="store_true", help="启用 checkpoint beam 搜索")
    parser.add_argument(
        "--search-config",
        type=Path,
        default=Path("config/search.json"),
        help="checkpoint 搜索配置 JSON",
    )


def _search_config(args: argparse.Namespace) -> Optional[SearchConfig]:
    if not getattr(args, "search", False):
        return None
    return SearchConfig.load(args.search_config)


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    genome = Genome.load(args.genome) if getattr(args, "genome", None) else Genome.default()
    elite_archive = EliteArchive.load(args.elite_archive) if args.elite_archive else None

    if args.command == "write-default-genome":
        genome.save(args.path)
        print(str(args.path))
        return 0

    if args.command == "summarize-eval":
        print(json.dumps(summarize_jsonl_logs(args.log_dir), indent=2, sort_keys=True))
        return 0

    if args.command == "promotion-gate":
        baseline = json.loads(args.baseline.read_text())
        candidate = json.loads(args.candidate.read_text())
        print(
            json.dumps(
                compare_eval_summaries(baseline, candidate, cohort=args.cohort),
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "build-replay":
        print(json.dumps(write_replay_cases(args.log_dir, args.output, args.limit), indent=2, sort_keys=True))
        return 0

    if args.command == "replay-query":
        cases = query_replay_cases(
            load_replay_cases(args.replay),
            phase=args.phase,
            case_type=args.case_type,
            limit=args.limit,
        )
        print(json.dumps({"cases": cases}, indent=2, sort_keys=True))
        return 0

    if args.command == "seed-cohorts":
        print(json.dumps(load_seed_config(args.seed_config), indent=2, sort_keys=True))
        return 0

    if args.command == "auto-evolve":
        result = AutoEvolution(
            AutoEvolutionConfig(
                root=args.root,
                mutator_command=args.mutator_command,
                evaluator=args.evaluator,
                test_command=args.test_command,
                run_root=args.run_root,
                baseline_eval_dirs=args.baseline_eval_dirs,
                effect_threshold=args.effect_threshold,
                min_samples=args.min_samples,
            )
        ).run()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.command == "measure":
        from balatro_agent.measure import measure_report

        report = measure_report(args.eval_dirs)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    client = BalatroBotClient(base_url=args.base_url, timeout=args.timeout)

    if args.command == "doctor":
        print(json.dumps(client.health(), indent=2, sort_keys=True))
        return 0

    if args.command == "start":
        print(json.dumps(client.start(deck=args.deck, stake=args.stake, seed=args.seed), indent=2))
        return 0

    if args.command == "step":
        runner = Runner(
            client,
            DefaultOrchestrator(genome),
            log_path=args.log,
            elite_archive=elite_archive,
        )
        action = runner.step()
        print(json.dumps(action.as_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "run":
        orchestrator = DefaultOrchestrator(genome)
        search_config = _search_config(args)
        planner = None
        if search_config is not None:
            planner = CheckpointSearchPlanner(
                client,
                DefaultOrchestrator(genome),
                genome,
                search_config,
            )
        runner = Runner(
            client,
            orchestrator,
            log_path=args.log,
            planner=planner,
            seed=args.seed,
            elite_archive=elite_archive,
        )
        print(json.dumps(runner.run(max_steps=args.max_steps, sleep_seconds=args.sleep), indent=2))
        return 0

    if args.command == "record":
        recorder = StateRecorder(
            client,
            args.output,
            include_raw=not args.summary_only,
            only_changes=not args.record_unchanged,
        )
        result = recorder.run(
            interval_seconds=args.interval,
            max_polls=args.max_polls,
            max_snapshots=args.max_snapshots,
            stop_on_game_over=not args.no_stop_on_game_over,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.command == "record-actions":
        recorder = ActionRecorder(client, args.output)
        result = recorder.run(
            interval_seconds=args.interval,
            max_polls=args.max_polls,
            stop_on_game_over=not args.no_stop_on_game_over,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.command == "eval":
        seeds = resolve_seed_list(args.seeds, args.seed_config, args.cohort)
        engine = EvolutionEngine(
            make_live_run_factory(
                args.base_url,
                args.deck,
                args.stake,
                args.max_steps,
                args.timeout,
                search_config=_search_config(args),
                elite_archive=elite_archive,
            )
        )
        result = engine.evaluate(genome, seeds or DEFAULT_SEEDS, args.log_dir)
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "evolve":
        seed_config = load_seed_config(args.seed_config)
        cohorts = seed_config["cohorts"]
        dev_seeds = args.seeds or list(cohorts.get("dev", []))
        regression_seeds = list(cohorts.get("regression", []))
        heldout_seeds = list(cohorts.get("heldout", []))
        if not dev_seeds or not regression_seeds or not heldout_seeds:
            raise ValueError("evolve requires non-empty dev, regression, and heldout cohorts")
        if args.sim:
            if args.sim_log_dir is None:
                raise ValueError("evolve --sim requires --sim-log-dir")
            from balatro_agent.sim_evolution import load_scenarios_from_logs, make_sim_run_factory

            scenarios = load_scenarios_from_logs(args.sim_log_dir)
            if not scenarios:
                raise ValueError(f"no SELECTING_HAND scenarios found in {args.sim_log_dir}")
            sim_factory = make_sim_run_factory(scenarios)
            engine = EvolutionEngine(
                sim_factory,
                rng=random.Random(args.random_seed),
                scenario_run_factory=sim_factory,
            )
            scenario_seeds = dev_seeds
        else:
            search_config = _search_config(args)
            scenario_library = CheckpointScenarioLibrary(args.output_dir / "scenarios", max_scenarios=18)
            live_factory = make_live_run_factory(
                args.base_url,
                args.deck,
                args.stake,
                args.max_steps,
                args.timeout,
                search_config=search_config,
                scenario_library=scenario_library,
                elite_archive=elite_archive,
            )
            scenario_steps = max((search_config or SearchConfig()).horizons.values())
            engine = EvolutionEngine(
                live_factory,
                rng=random.Random(args.random_seed),
                scenario_run_factory=make_checkpoint_run_factory(
                    args.base_url,
                    scenario_steps,
                    args.timeout,
                    search_config=search_config,
                ),
            )
            scenario_seeds = scenario_library.freeze
        result = engine.evolve_staged(
            genome,
            generations=args.generations,
            population=args.population,
            scenario_seeds=scenario_seeds,
            dev_seeds=dev_seeds,
            regression_seeds=regression_seeds,
            heldout_seeds=heldout_seeds,
            output_dir=args.output_dir,
        )
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
        return 0

    raise AssertionError(f"未处理的命令：{args.command}")
