# Turning customer requirements into a design

What to extract from a requirements document, and what to ask when it is missing.

## Information to extract
Expected users and peak concurrent users or requests per second. Data volume now and growth per year. Latency and availability targets (SLA, RTO, RPO). Compliance or data residency constraints, including the required region. Traffic pattern: steady, daily peaks, or spiky campaigns. Existing technology constraints such as language, database engine or container usage. Budget limit or cost priority.

## Questions to ask when information is missing
What is the peak requests per second, and the average and peak size of a request? How large is the dataset and how fast does it grow? Which availability target applies, and is a short outage acceptable? Are there compliance requirements (GDPR, HIPAA, PCI) or region restrictions? Is the load constant or spiky? Which technologies must be used or avoided?

## Handling missing data
Never invent numbers. State each assumption explicitly in the recommendation, give the sizing as a starting point to validate with a load test, and list the open questions. When the requirements conflict (for example very high availability with a very small budget), point out the conflict and show the trade-off.
