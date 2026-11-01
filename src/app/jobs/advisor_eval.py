"""Run the advisor on every evaluation case and print a report.

    python -m app.jobs.advisor_eval [--runs 3]

Uses the real LLM and the knowledge base in the database, so it costs a few cents
per run. Several runs per case show how stable the answers are.
"""
import argparse
import asyncio
import sys

from app.core.database import async_session, engine
from app.services.advisor_eval import load_cases, score_plan, summarise_runs
from app.services.advisor_service import AdvisorError, recommend
from app.services.llm_client import LLMError, get_llm_client


async def run(llm, session_factory=async_session, cases=None, runs: int = 1) -> list:
    summaries = []
    for case in cases or load_cases():
        scored = []
        for _ in range(runs):
            async with session_factory() as db:
                try:
                    result = await recommend(db, llm, case["requirements"])
                except (AdvisorError, LLMError) as exc:
                    scored.append({"name": case["name"], "coverage": 0.0, "missing": ["error"], "forbidden": [],
                                   "warnings": [str(exc)], "open_questions": 0, "open_questions_ok": False,
                                   "passed": False})
                    continue
            scored.append(score_plan(case, result.plan.model_dump(), result.warnings))
        summaries.append(summarise_runs(case["name"], scored))
    return summaries


def format_report(results: list) -> str:
    lines = []
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        extra = f" missing={r['missing']}" if r["missing"] else ""
        extra += f" forbidden={r['forbidden']}" if r["forbidden"] else ""
        extra += "" if r["open_questions_ok"] else " too_few_open_questions"
        for warning in r["warnings"]:
            extra += f"\n      ! {warning}"
        lines.append(f"{status} {r['name']:<18} coverage={r['coverage']:.0%} runs={r['passes']}/{r['runs']}{extra}")
    average = sum(r["coverage"] for r in results) / len(results) if results else 0.0
    lines.append(f"average coverage: {average:.0%}, passed {sum(r['passed'] for r in results)}/{len(results)} cases")
    return "\n".join(lines)


async def main(runs: int) -> int:
    try:
        llm = get_llm_client()
    except LLMError as exc:
        print(f"Cannot run: {exc}")
        return 1
    try:
        results = await run(llm, runs=runs)
    finally:
        await llm.aclose()
        await engine.dispose()
    print(format_report(results))
    return 0 if all(r["passed"] for r in results) else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1, choices=range(1, 11))
    sys.exit(asyncio.run(main(parser.parse_args().runs)))
