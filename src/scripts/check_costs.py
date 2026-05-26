import boto3
import json
import os
import urllib.request
from datetime import datetime, timedelta

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
ALERT_EMAIL        = os.environ.get("ALERT_EMAIL", "")
ENVIRONMENT        = os.environ.get("ENVIRONMENT", "dev")
BUDGET_LIMIT       = float(os.environ.get("BUDGET_LIMIT", "30"))
ANOMALY_THRESHOLD  = float(os.environ.get("ANOMALY_THRESHOLD", "10"))

TODAY       = datetime.utcnow().strftime("%Y-%m-%d")
YESTERDAY   = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
MONTH_START = datetime.utcnow().replace(day=1).strftime("%Y-%m-%d")


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
    budget_percent = round((mtd_cost / BUDGET_LIMIT) * 100, 1)
    services_text  = "\n".join(f"  • {s['name']}: `${s['cost']}`" for s in top_services)

    if mtd_cost >= BUDGET_LIMIT:
        emoji = "🚨"
        alert = f"*BUDGET EXCEEDED!* MTD `${mtd_cost}` reached the `${BUDGET_LIMIT}` limit!"
    elif mtd_cost >= BUDGET_LIMIT * 0.8:
        emoji = "⚠️"
        alert = f"*80% budget used!* MTD `${mtd_cost}` of `${BUDGET_LIMIT}`."
    elif yesterday_cost >= ANOMALY_THRESHOLD:
        emoji = "🔍"
        alert = f"*Cost anomaly!* Yesterday `${yesterday_cost}` exceeds threshold `${ANOMALY_THRESHOLD}`."
    else:
        emoji = "✅"
        alert = ""

    if alert:
        send_telegram(
            f"{emoji} *AWS Cost Alert — {ENVIRONMENT.upper()}*\n\n"
            f"{alert}\n\n"
            f"💰 MTD: `${mtd_cost}` / `${BUDGET_LIMIT}` ({budget_percent}%)\n"
            f"📈 Yesterday: `${yesterday_cost}`\n\n"
            f"*Top services:*\n{services_text}\n\n"
            f"[AWS Cost Explorer](https://console.aws.amazon.com/cost-management/home)"
        )
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