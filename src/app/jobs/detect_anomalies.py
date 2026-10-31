import argparse
import asyncio
import logging
import os
import sys
from sqlalchemy import select
from app.core.database import async_session, engine
from app.models.aws_account import AWSaccount
from app.services.anomaly_runner import analyze_account, store_anomalies

logger = logging.getLogger("anomaly-job")


async def run(days: int, session_factory=async_session) -> int:
    async with session_factory() as db:
        accounts = (
            await db.execute(select(AWSaccount).where(AWSaccount.is_active.is_(True)))
        ).scalars().all()

    logger.info("Analysing %d active account(s), last %d days", len(accounts), days)
    failures = 0
    for account in accounts:
        label = account.aws_account_id
        try:
            result = await analyze_account(account, days)
            async with session_factory() as db:
                await store_anomalies(db, account, result)
            logger.info(
                "Account %s: %d service(s) analysed, %d anomaly(ies) stored",
                label, result.services_analyzed, len(result.anomalies),
            )
        except Exception:
            failures += 1
            logger.exception("Account %s: anomaly detection failed", label)
    return failures

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=int(os.getenv("ANOMALY_DAYS", "90")))
    args = parser.parse_args()
    if not 21 <= args.days <= 365:
        parser.error("--days must be between 21 and 365")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    async def _main() -> int:
        try:
            return await run(args.days)
        finally:
            await engine.dispose()

    sys.exit(1 if asyncio.run(_main()) else 0)


if __name__ == "__main__":
    main()
