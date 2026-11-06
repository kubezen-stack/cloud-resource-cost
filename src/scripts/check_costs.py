import asyncio
import boto3
import json
import os
import urllib.request
from datetime import datetime, timedelta

from app.services.anomaly_advice import advise, format_advice
from app.services.anomaly_alerts import anomalies_on, describe
from app.services.anomaly_explain import describe_drivers, explain_spike, parse_usage_costs
from app.services.anomaly_service import BASELINE_WINDOW, detect_anomalies
from app.services.llm_client import client_from_env

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
ALERT_EMAIL        = os.environ.get("ALERT_EMAIL", "")
ENVIRONMENT        = os.environ.get("ENVIRONMENT", "dev")
BUDGET_LIMIT       = float(os.environ.get("BUDGET_LIMIT", "30"))
ANOMALY_THRESHOLD  = float(os.environ.get("ANOMALY_THRESHOLD", "10"))

TODAY       = datetime.utcnow().strftime("%Y-%m-%d")
YESTERDAY   = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
MONTH_START = datetime.utcnow().replace(day=1).strftime("%Y-%m-%d")

# Days of history given to the anomaly detector (it needs at least 21).
HISTORY_DAYS  = 90
HISTORY_START = (datetime.utcnow() - timedelta(days=HISTORY_DAYS)).strftime("%Y-%m-%d")
# Cost Explorer settles a day late, so the job reports the day before yesterday.
REPORT_DAY    = (datetime.utcnow() - timedelta(days=2)).date()
# Every explained anomaly costs one more Cost Explorer request, so only the biggest are explained.
MAX_EXPLAINED = 3


def get_costs():
    ce = boto3.client("ce", region_name="us-east-1")

    mtd = ce.get_cost_and_usage(
        TimePeriod={"Start": MONTH_START, "End": TODAY},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
    )
    yesterday = ce.get_cost_and_usage(
        TimePeriod={"Start": YESTERDAY, "End": TODAY},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
    )
    by_service = ce.get_cost_and_usage(
        TimePeriod={"Start": MONTH_START, "End": TODAY},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )

    mtd_cost       = round(float(mtd["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"]), 2)
    yesterday_cost = round(float(yesterday["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"]), 2)
    top_services   = sorted(
        [
            {"name": g["Keys"][0], "cost": round(float(g["Metrics"]["UnblendedCost"]["Amount"]), 2)}
            for g in by_service["ResultsByTime"][0]["Groups"]
            if float(g["Metrics"]["UnblendedCost"]["Amount"]) > 0
        ],
        key=lambda x: x["cost"],
        reverse=True,
    )[:5]

    return mtd_cost, yesterday_cost, top_services


def cost_explorer_pages(**params):
    """All result periods of a Cost Explorer query, following the pagination token."""
    ce = boto3.client("ce", region_name="us-east-1")
    results = []
    while True:
        page = ce.get_cost_and_usage(**params)
        results.extend(page["ResultsByTime"])
        token = page.get("NextPageToken")
        if not token:
            return results
        params["NextPageToken"] = token


def get_daily_service_costs():
    return cost_explorer_pages(
        TimePeriod={"Start": HISTORY_START, "End": TODAY},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )


def get_usage_costs(service, day):
    """Daily costs of one service by usage type and region: the day and the baseline before it."""
    return cost_explorer_pages(
        TimePeriod={"Start": str(day - timedelta(days=BASELINE_WINDOW)), "End": str(day + timedelta(days=1))},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
        Filter={"Dimensions": {"Key": "SERVICE", "Values": [service]}},
        GroupBy=[{"Type": "DIMENSION", "Key": "USAGE_TYPE"}, {"Type": "DIMENSION", "Key": "REGION"}],
    )


def find_drivers(anomaly):
    """The usage types behind an anomaly, or None when they cannot be found (the alert still goes out)."""
    try:
        series = parse_usage_costs(get_usage_costs(anomaly.service, anomaly.day))
        return explain_spike(series, anomaly.day)
    except Exception as exc:
        print(f"Could not explain the anomaly of {anomaly.service}: {exc}")
        return None


async def _advise(llm, anomaly, drivers):
    try:
        return await advise(llm, anomaly, drivers)
    finally:
        await llm.aclose()


def get_advice(anomaly, drivers):
    """Possible causes and next steps from the model, or None (no API key, no facts, no valid answer)."""
    if not drivers:
        return None
    llm = client_from_env()
    if llm is None:
        return None
    try:
        return format_advice(asyncio.run(_advise(llm, anomaly, drivers)))
    except Exception as exc:
        print(f"Advice skipped: {exc}")
        return None


def find_anomalies():
    """Anomalies of REPORT_DAY, or None when the check could not run (the report still goes out)."""
    try:
        return anomalies_on(detect_anomalies(get_daily_service_costs()), REPORT_DAY)
    except Exception as exc:
        print(f"Anomaly check skipped: {exc}")
        return None


def send_telegram(message):
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req)


def send_email(subject, body):
    if not ALERT_EMAIL:
        return
    boto3.client("ses", region_name="us-east-1").send_email(
        Source=ALERT_EMAIL,
        Destination={"ToAddresses": [ALERT_EMAIL]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": body}},
        },
    )


def set_output(name, value):
    output_file = os.environ.get("GITHUB_OUTPUT", "")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{name}={value.replace(chr(10), chr(92) + 'n')}\n")


def main():
    mtd_cost, yesterday_cost, top_services = get_costs()
    anomalies = find_anomalies()
    advice = None
    budget_percent = round((mtd_cost / BUDGET_LIMIT) * 100, 1)
    services_text  = "\n".join(f"  • {s['name']}: `${s['cost']}`" for s in top_services)

    if mtd_cost >= BUDGET_LIMIT:
        emoji = "🚨"
        alert = f"*BUDGET EXCEEDED!* MTD `${mtd_cost}` reached the `${BUDGET_LIMIT}` limit!"
    elif mtd_cost >= BUDGET_LIMIT * 0.8:
        emoji = "⚠️"
        alert = f"*80% budget used!* MTD `${mtd_cost}` of `${BUDGET_LIMIT}`."
    elif anomalies:
        emoji = "🔍"
        biggest = sorted(anomalies, key=lambda a: a.actual_cost - a.expected_cost, reverse=True)
        found = [find_drivers(a) if i < MAX_EXPLAINED else None for i, a in enumerate(biggest)]
        lines = [describe(a) + (f" — {describe_drivers(d)}" if d else "") for a, d in zip(biggest, found)]
        alert = f"*Unusual cost on {REPORT_DAY}:* " + "; ".join(lines)
        advice = get_advice(biggest[0], found[0])
    elif yesterday_cost >= ANOMALY_THRESHOLD:
        emoji = "🔍"
        alert = f"*Cost anomaly!* Yesterday `${yesterday_cost}` exceeds threshold `${ANOMALY_THRESHOLD}`."
    else:
        emoji = "✅"
        alert = ""

    def compose(with_advice):
        return (
            f"{emoji} *AWS Cost Alert — {ENVIRONMENT.upper()}*\n\n"
            f"{alert}\n\n"
            + (f"{with_advice}\n\n" if with_advice else "")
            + f"💰 MTD: `${mtd_cost}` / `${BUDGET_LIMIT}` ({budget_percent}%)\n"
            f"📈 Yesterday: `${yesterday_cost}`\n\n"
            f"*Top services:*\n{services_text}\n\n"
            f"[AWS Cost Explorer](https://console.aws.amazon.com/cost-management/home)"
        )

    if alert:
        sent = False
        if advice:
            try:
                send_telegram(compose(advice))
                sent = True
            except Exception as exc:
                print(f"Telegram refused the alert with advice, sending it without: {exc}")
        if not sent:
            send_telegram(compose(None))
        send_email(
            subject=f"[{ENVIRONMENT.upper()}] AWS Cost Alert — {budget_percent}% budget used",
            body=f"MTD: ${mtd_cost} / ${BUDGET_LIMIT} ({budget_percent}%)\nYesterday: ${yesterday_cost}\n\n{alert}",
        )

    set_output("mtd_cost",       str(mtd_cost))
    set_output("yesterday_cost", str(yesterday_cost))
    set_output("budget_percent", str(budget_percent))
    set_output("period",         f"{MONTH_START} → {TODAY}")
    set_output("status_emoji",   emoji)
    set_output("alert_message",  alert)
    set_output("top_services",   services_text)


if __name__ == "__main__":
    main()