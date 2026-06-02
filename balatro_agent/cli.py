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
from balatro_agent.client import DEFAULT_BASE_URL, BalatroBotClient
from balatro_agent.evolution import EvolutionEngine, make_live_run_factory
from balatro_agent.model import Genome
from balatro_agent.orchestrator import DefaultOrchestrator
from balatro_agent.recorder import StateRecorder
from balatro_agent.runner import Runner
from balatro_agent.seeds import DEFAULT_SEEDS, load_seed_config, resolve_seed_list


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="balatro-agent",
        description="通过 BalatroBot 运行、评估和进化 Balatro 自动化 agent。",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="BalatroBot JSON-RPC 地址")
    parser.add_argument("--timeout", type=float, default=10.0, help="请求超时时间（秒）")
    parser.add_argument("--genome", type=Path, default=None, help="可选的 genome JSON 路径")

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

    record = subparsers.add_parser("record", help="只读记录人类游玩时的 BalatroBot 状态变化")
    record.add_argument("--output", type=Path, default=Path("runs/human/record.jsonl"), help="输出 JSONL 路径")
    record.add_argument("--interval", type=float, default=1.0, help="轮询间隔秒数")
    record.add_argument("--max-polls", type=int, default=None, help="最多轮询次数；默认一直运行")
    record.add_argument("--max-snapshots", type=int, default=None, help="最多写入的状态快照数；默认不限")
    record.add_argument("--record-unchanged", action="store_true", help="记录每次轮询，而不只记录状态变化")
    record.add_argument("--summary-only", action="store_true", help="只写状态摘要，不写原始 BalatroBot 状态")
    record.add_argument("--no-stop-on-game-over", action="store_true", help="遇到 GAME_OVER 后继续记录")

    eval_cmd = subparsers.add_parser("eval", help="在多个 seed 上评估一个 genome")
    eval_cmd.add_argument("--deck", default="RED", help="牌组常量，例如 RED")
    eval_cmd.add_argument("--stake", default="WHITE", help="赌注常量，例如 WHITE")
    eval_cmd.add_argument("--seeds", nargs="*", default=None, help="评估用 seed 列表")
    eval_cmd.add_argument("--seed-config", type=Path, default=None, help="seed cohort 配置文件")
    eval_cmd.add_argument("--cohort", default="dev", help="从 seed 配置中选择的 cohort")
    eval_cmd.add_argument("--max-steps", type=int, default=500, help="每个 seed 的最大步数")
    eval_cmd.add_argument("--log-dir", type=Path, default=Path("runs/eval"), help="评估日志目录")

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
    evolve.add_argument("--seed-config", type=Path, default=None, help="seed cohort 配置文件")
    evolve.add_argument("--cohort", default="dev", help="从 seed 配置中选择的 cohort")
    evolve.add_argument("--generations", type=int, default=3, help="进化代数")
    evolve.add_argument("--population", type=int, default=6, help="每代候选数量")
    evolve.add_argument("--max-steps", type=int, default=500, help="每个 seed 的最大步数")
    evolve.add_argument("--output-dir", type=Path, default=Path("runs/evolution"), help="进化输出目录")
    evolve.add_argument("--random-seed", type=int, default=1, help="进化随机数 seed")

    genome = subparsers.add_parser("write-default-genome", help="写入默认 genome JSON")
    genome.add_argument("path", type=Path, help="输出路径")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    genome = Genome.load(args.genome) if getattr(args, "genome", None) else Genome.default()

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

    client = BalatroBotClient(base_url=args.base_url, timeout=args.timeout)

    if args.command == "doctor":
        print(json.dumps(client.health(), indent=2, sort_keys=True))
        return 0

    if args.command == "start":
        print(json.dumps(client.start(deck=args.deck, stake=args.stake, seed=args.seed), indent=2))
        return 0

    if args.command == "step":
        runner = Runner(client, DefaultOrchestrator(genome), log_path=args.log)
        action = runner.step()
        print(json.dumps(action.as_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "run":
        runner = Runner(client, DefaultOrchestrator(genome), log_path=args.log)
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

    if args.command == "eval":
        seeds = resolve_seed_list(args.seeds, args.seed_config, args.cohort)
        engine = EvolutionEngine(
            make_live_run_factory(
                args.base_url,
                args.deck,
                args.stake,
                args.max_steps,
                args.timeout,
            )
        )
        result = engine.evaluate(genome, seeds or DEFAULT_SEEDS, args.log_dir)
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "evolve":
        seeds = resolve_seed_list(args.seeds, args.seed_config, args.cohort)
        engine = EvolutionEngine(
            make_live_run_factory(
                args.base_url,
                args.deck,
                args.stake,
                args.max_steps,
                args.timeout,
            ),
            rng=random.Random(args.random_seed),
        )
        result = engine.evolve(
            genome,
            args.generations,
            args.population,
            seeds or DEFAULT_SEEDS,
            args.output_dir,
        )
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
        return 0

    raise AssertionError(f"未处理的命令：{args.command}")
