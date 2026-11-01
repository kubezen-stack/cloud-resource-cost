import asyncio
import sys

from app.core.database import async_session, engine
from app.services.advisor_eval import load_cases, score_plan
from app.services.advisor_service import AdvisorError, recommend
from app.services.llm_client import LLMError, get_llm_client


async def run(llm, session_factory=async_session, cases=None) -> list:
    results = []
    for case in cases or load_cases():
        async with session_factory() as db:
            try:
                response = await recommend(db, llm, case["requirements"])
            except (AdvisorError, LLMError) as exc:
                results.append({"name": case["name"], "coverage": 0.0, "missing": ["error"],
                                "forbidden": [], "open_questions": 0, "open_questions_ok": False,
                                "passed": False, "error": str(exc)})
                continue
        results.append(score_plan(case, response.plan.model_dump()))
    return results


def format_report(results: list) -> str:
    lines = []
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        extra = f" missing={r['missing']}" if r["missing"] else ""
        extra += f" forbidden={r['forbidden']}" if r["forbidden"] else ""
        extra += "" if r["open_questions_ok"] else f" open_questions={r['open_questions']}"
        lines.append(f"{status} {r['name']:<18} coverage={r['coverage']:.0%}{extra}")
    average = sum(r["coverage"] for r in results) / len(results) if results else 0.0
    lines.append(f"average coverage: {average:.0%}, passed {sum(r['passed'] for r in results)}/{len(results)}")
    return "\n".join(lines)


async def main() -> int:
    try:
        llm = get_llm_client()
    except LLMError as exc:
        print(f"Cannot run: {exc}")
        return 1
    try:
        results = await run(llm)
    finally:
        await llm.aclose()
        await engine.dispose()
    print(format_report(results))
    return 0 if all(r["passed"] for r in results) else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
