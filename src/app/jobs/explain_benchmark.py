"""Compare ways of naming the usage type behind a cost spike on synthetic services.

    python -m app.jobs.explain_benchmark [--trials 500]

Needs no database, network or API key. The result is deterministic for a given --trials.
"""
import argparse

from app.services.explain_benchmark import evaluate, format_report


def main(trials: int) -> int:
    print(format_report(evaluate(trials), trials))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--trials", type=int, default=500, help="generated services per scenario")
    raise SystemExit(main(parser.parse_args().trials))
