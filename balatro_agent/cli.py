from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import List, Optional

from balatro_agent.analysis import summarize_jsonl_logs
from balatro_agent.client import DEFAULT_BASE_URL, BalatroBotClient
from balatro_agent.evolution import EvolutionEngine, make_live_run_factory
from balatro_agent.model import Genome
from balatro_agent.orchestrator import DefaultOrchestrator
from balatro_agent.runner import Runner


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

    eval_cmd = subparsers.add_parser("eval", help="在多个 seed 上评估一个 genome")
    eval_cmd.add_argument("--deck", default="RED", help="牌组常量，例如 RED")
    eval_cmd.add_argument("--stake", default="WHITE", help="赌注常量，例如 WHITE")
    eval_cmd.add_argument("--seeds", nargs="*", default=["AGENT1", "AGENT2", "AGENT3"], help="评估用 seed 列表")
    eval_cmd.add_argument("--max-steps", type=int, default=500, help="每个 seed 的最大步数")
    eval_cmd.add_argument("--log-dir", type=Path, default=Path("runs/eval"), help="评估日志目录")

    summarize = subparsers.add_parser("summarize-eval", help="汇总 JSONL 评估日志")
    summarize.add_argument("--log-dir", type=Path, default=Path("runs/eval"), help="评估日志目录或单个 JSONL 文件")

    evolve = subparsers.add_parser("evolve", help="变异策略权重并保留最佳结果")
    evolve.add_argument("--deck", default="RED", help="牌组常量，例如 RED")
    evolve.add_argument("--stake", default="WHITE", help="赌注常量，例如 WHITE")
    evolve.add_argument("--seeds", nargs="*", default=["AGENT1", "AGENT2", "AGENT3"], help="评估用 seed 列表")
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

    if args.command == "eval":
        engine = EvolutionEngine(
            make_live_run_factory(
                args.base_url,
                args.deck,
                args.stake,
                args.max_steps,
                args.timeout,
            )
        )
        result = engine.evaluate(genome, args.seeds, args.log_dir)
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "evolve":
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
            args.seeds,
            args.output_dir,
        )
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
        return 0

    raise AssertionError(f"未处理的命令：{args.command}")
