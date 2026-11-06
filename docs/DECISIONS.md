# Design decisions

Short records of the choices that shape the project: what was decided, why, and what it costs.
Newest topics last. Numbers come from the evaluation runs described in each entry.

## 1. The model proposes, code verifies

**Decision.** The AI architecture advisor asks the LLM for a plan, then checks and fixes the capacity
numbers in code (`services/capacity.py`) instead of trusting the model's arithmetic.

**Why.** A plan can read well and still be wrong: too few vCPUs for the stated traffic, a single zone
for a "high availability" request, a database without backups. Asking the model to fix its own plan
did not converge in evaluation (it kept answering 32 vCPUs when the requirement was 48). Rules that
can be written as arithmetic are cheaper and more reliable in code.

**What the code decides.** Required vCPUs from peak requests per second, CPU milliseconds per request
and target utilisation; the extra headroom needed to survive losing one zone; minimum instance count
(a multiple of the zone count); data tier completeness (instance class, storage size, Multi-AZ,
backups, cache replicas); security baseline for multi-zone plans.

**Repair versus planning.** The first version rewrote the model's instance counts when they were wrong.
That worked but read as a patch on a bad answer. It was replaced by a planner: instance counts are
derived from the capacity inputs, and the model's proposal is only used as a floor (a larger proposal
is never lowered). The response says when the planner changed the numbers.

**Trade-off.** The planner handles one compute tier. Plans with several compute tiers are verified
and sent back to the model once, not planned.

## 2. Retrieval over a curated catalog, in PostgreSQL

**Decision.** The advisor answers from a curated markdown catalog (84 chunks). Embeddings
(`text-embedding-3-small`) are stored as JSON in PostgreSQL and compared with cosine similarity in
numpy. No vector database.

**Why.** The corpus is small and changes with the code, so a separate service would add operations
work and nothing else. `ingest_knowledge` is idempotent: it keeps a content hash per chunk and only re-embeds chunks
that are new or changed (or when the embedding model changed).

**Trade-off.** Similarity search is linear. It is fine for hundreds of chunks and would need an index
(pgvector or similar) for tens of thousands.

## 3. One retrieval probe per topic

**Decision.** `retrieve_multi` runs the customer's text plus nine topic probes (compute, database,
networking and delivery, storage, caching and messaging, security, monitoring, environments and
availability, cost optimisation), takes the top three chunks of each and caps the context at 14 chunks.

**Why.** One similarity search for the whole request favours whatever the request talks about most,
usually compute. A probe per topic gives each area a place in the context, so the plan has material
for cache, queues, monitoring and security even when the customer did not mention them.

## 4. Strict output schema, tolerant of harmless variation

**Decision.** The plan is a JSON object validated with pydantic, with one retry that tells the model
which field and which type failed (never echoing its own content back). Citations that do not
match a retrieved chunk are dropped, and a component left with no citation is downgraded from
`catalog` to `general_knowledge`.

**Why tolerant.** Early evaluation failures were schema noise, not wrong advice: `role: "queue"`,
`peak_rps_source: "derived"`, a capacity object with null numbers. Free-text vocabulary is normalised
(unknown role becomes `other`, any source other than `customer` becomes `assumption`), and a capacity
object without numbers is treated as unknown, which in turn produces an open question.

**Prompt injection.** User requirements are fenced as data in the prompt, and the evaluation set
includes an injection case whose output must not contain the injected instruction's payload.

## 4a. Model choice

**Decision.** `gpt-4o` for plans (`helm/cost-optimizer/values.yaml: llm.model`).

**Why.** Plan accuracy mattered more than price per call, and the evaluation set (decision 5) is the
check that the choice holds. The cheaper model stays available for quick runs
(`LLM_MODEL=gpt-4o-mini`).

## 5. Automatic evaluation instead of reading answers

**Decision.** `eval_cases.json` holds five cases (e-commerce, internal tool, spiky sales, vague
request, prompt injection). `python -m app.jobs.advisor_eval --runs N` runs each case N times and
scores topic coverage, forbidden content, minimum open questions and, where required, the capacity
checks. Scoring reads plan values only, not field names, so keywords in the schema cannot satisfy a topic.

**Why.** Reading one answer says little about a stochastic system. Repeated runs show stability:
the final version passes 5/5 cases and 15/15 runs.

**Lessons recorded.** A failing case was caused by the case itself (no traffic numbers, so the
model correctly left capacity empty); the case was fixed, not the model. A "vague request" plan once
had no data store; the prompt now requires one.

**Cost.** About 30–50 cents per `--runs 3` on `gpt-4o`.

## 6. Cost estimates come from the AWS Price List API

**Decision.** `POST /advisor/cost` prices a plan from the live Price List API (`pricing:GetProducts`)
instead of a price table in the repository. Results are cached in process for 24 hours.

**Why.** Hard-coded prices are wrong within months and region-specific. Verified against the live API
for `eu-central-1` (ALB, EC2, RDS Multi-AZ, gp3 storage, ElastiCache, NAT Gateway).

**How totals are built.**
- Fixed charges only, list price, 730 hours per month. Compute is counted at the minimum instance count;
  the upper bound counts every instance at the maximum for the whole month. The real bill lies between
  them depending on how long peaks last.
- Usage-based charges (LCU, data processed, requests) are listed with their unit price but excluded from totals.
- Services without a published fixed price (CloudFront, S3, SQS, WAF, KMS, CloudWatch) are listed as usage-based, never guessed.
- A NAT Gateway per zone is added and marked as assumed when the plan uses private subnets.
- Not included: server disks, data transfer, support plans (stated in the response notes).

**Savings alternatives.** 1-year standard reserved (no upfront), Graviton equivalents (m5/m6i to m6g and similar),
and both together. Each alternative lists its caveats (commitment, arm64 builds). Where a reserved price is
not offered (for example some cache nodes) the line stays at on-demand and says so.

**Limits.** Region names are mapped for 15 regions; only `eu-central-1` has been checked against the live API.

## 7. Separate IAM policy for pricing

**Decision.** The Price List permission lives in its own policy (`pricing_policy`, variable
`enable_pricing_api`, default on) instead of inside the Cost Explorer policy.

**Why.** The Cost Explorer policy is created only when `enable_cost_explorer` is true, and it is off
in the stage environment. The first version put the pricing statement there, so it silently never
reached the node role. Independent features get independent switches.

## 8. Customer AWS accounts through an assumed role with an external ID

**Decision.** The application reads customer cost data by assuming an IAM role in the customer's
account with an `ExternalId`, and stores no long-term customer credentials.

**Why.** The external ID protects against the confused-deputy problem: another tenant cannot trick the
service into using a role that was created for someone else.

## 9. Anomaly detection: robust baseline, forest for ranking, guardrails for decisions

**Decision.** For each service the expected cost is the rolling median of the previous 14 days. An
Isolation Forest ranks days by how unusual their deviation is, and guardrails decide what is reported:
at least +50%, at least $1 and at least four robust standard deviations above the baseline.

**Why.** Measured on 420 synthetic series ([experiments/anomaly-detection.md](experiments/anomaly-detection.md)):
precision 1.00 and recall 0.92 for the hybrid, against 0.49/0.67 for a rolling z-score, 0.67/0.94 for
median + MAD and 0.43/0.95 for an Isolation Forest alone. Recall is about equal; the difference is false
alarms. The forest alone flags a fixed share of days whether or not anything happened, and mean-based
baselines are fooled by growth and by multi-day plateaus.

**Trade-off.** Small spikes on noisy bills (x1.6 on a 20% noisy series) are not reported on purpose.

**Limit.** Only increases are reported. The guardrails were tuned on the same kinds of synthetic series
as the benchmark, so the precision is optimistic and needs confirmation on real billing history.

## 9a. Explaining a spike with facts, not guesses

**Decision.** When the detector finds an anomaly, the daily notification names the usage types behind it
(one more Cost Explorer request per anomaly, at most three per run). The method is plain arithmetic:
increase over the 14-day median per usage type and region, largest first. No model is involved.

**Why.** "EC2 cost $160 instead of $51" leaves the reader to find the cause in the console. Ranking by
dollars rather than by relative growth keeps tiny noisy lines from outranking the one that cost $30 more.
Measured on synthetic services ([experiments/spike-attribution.md](experiments/spike-attribution.md)):
the right usage type is named first in 96% of cases on average, against 12% for "the biggest line of the bill"
and 91% for relative growth, which is better only when a single small line is the whole story.

**Limits.** It says what grew, not why. A later step can let a model turn these facts into hypotheses and
actions, constrained by them.

## 10. Rightsizing from CPU only

**Decision.** Instance advice uses hourly average and maximum CPU from CloudWatch over at least seven
days: idle, downsize one step, upsize, or keep. A downsize is proposed only if the projected p95 stays
under 60% and the projected maximum under 95%.

**Why.** Memory is not part of the default CloudWatch metrics, so memory-bound workloads cannot be
judged. The response says that. Projecting after the downsize, instead of checking the current load,
is what keeps a "keep" from turning into a throttled instance.

## 11. Stage is disposable

**Decision.** The stage environment is created with Terraform and Ansible when needed and destroyed
when idle (two `t3.medium` nodes cost about $2 a day).

**Consequences handled in code and runbook.**
- The runner name is derived from the Elastic IP, which survives recreation, so a stale registration
  exists in GitHub. The runner is registered with `--replace`, and the registration token is passed
  through the environment so it stays out of the logs.
- After the database is recreated: run `ingest_knowledge` and register a user again.
- The public host is `stage.<elastic-ip>.sslip.io` with Let's Encrypt staging certificates, so no
  domain is needed.

## Known gaps

- Cost forecasting uses the Cost Explorer forecast API; the project has no forecasting model of its own to evaluate.
- `ingest_knowledge` is a manual step after deployment; it should become a Helm hook or a pipeline step.
- The evaluation is not part of CI because it calls a paid API.
- Peak duration is not an input of the cost estimate, so it reports a range instead of one expected figure.
