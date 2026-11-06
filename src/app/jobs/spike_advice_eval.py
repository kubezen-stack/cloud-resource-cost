"""Check the quality of the advice given for cost spikes, on cases with a known cause.

    LLM_API_KEY=... python -m app.jobs.spike_advice_eval [--runs 1] [--case NAME]

Needs only an API key (LLM_MODEL picks the model, gpt-4o by default). No database. Every run costs
a few cents: one request per case and run.
"""
import argparse
import asyncio

from app.services.advisor_eval import summarise_runs
from app.services.anomaly_advice import AdviceError, advise, load_playbook
from app.services.anomaly_advice_eval import case_inputs, failed_run, load_cases, score_advice
from app.services.llm_client import LLMError, client_from_env


async def run(llm, runs: int, cases=None) -> list:
    playbook = load_playbook()
    summaries = []
    for case in cases or load_cases():
        anomaly, drivers = case_inputs(case)
        scored = []
        for _ in range(runs):
            try:
                scored.append(score_advice(case, await advise(llm, anomaly, drivers, playbook)))
            except (AdviceError, LLMError) as exc:
                scored.append(failed_run(case, str(exc)))
        summaries.append(summarise_runs(case["name"], scored))
    return summaries


def format_report(results: list) -> str:
    lines = []
    for r in results:
        extra = f" missing={r['missing']}" if r["missing"] else ""
        extra += f" forbidden={r['forbidden']}" if r["forbidden"] else ""
        extra += "" if r["open_questions_ok"] else " too_few_questions"
        extra += "".join(f"\n      ! {w}" for w in r["warnings"])
        lines.append(f"{'PASS' if r['passed'] else 'FAIL'} {r['name']:<20} coverage={r['coverage']:.0%} "
                     f"runs={r['passes']}/{r['runs']}{extra}")
    average = sum(r["coverage"] for r in results) / len(results) if results else 0.0
    lines.append(f"average coverage: {average:.0%}, passed {sum(r['passed'] for r in results)}/{len(results)} cases")
    return "\n".join(lines)


def select_cases(name=None) -> list:
    """All cases, or the one called `name` (ValueError with the known names if there is none)."""
    cases = load_cases()
    if name is None:
        return cases
    chosen = [c for c in cases if c["name"] == name]
    if not chosen:
        raise ValueError(f"Unknown case '{name}'. Cases: {', '.join(c['name'] for c in cases)}")
    return chosen


async def main(runs: int, case=None) -> int:
    llm = client_from_env()
    if llm is None:
        print("Cannot run: LLM_API_KEY is not set")
        return 1
    try:
        cases = select_cases(case)
    except ValueError as exc:
        print(exc)
        await llm.aclose()
        return 1
    try:
        results = await run(llm, runs, cases)
    finally:
        await llm.aclose()
    print(format_report(results))
    return 0 if all(r["passed"] for r in results) else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=1, help="answers requested per case")
    parser.add_argument("--case", help="run only this case")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.runs, args.case)))
