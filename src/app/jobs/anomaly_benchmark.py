"""Compare the anomaly detector with simpler methods on synthetic series.

    python -m app.jobs.anomaly_benchmark [--series 20]

Needs no database, network or API key. The result is deterministic for a given --series.
"""
import argparse

from app.services.anomaly_benchmark import build_cases, evaluate, format_report


def main(series: int) -> int:
    print(format_report(evaluate(build_cases(series)), series))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--series", type=int, default=20, help="generated series per scenario and injection")
    raise SystemExit(main(parser.parse_args().series))
