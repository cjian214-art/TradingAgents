# Safe research automation

## GitHub Actions

`.github/workflows/universe-research.yml` has only a manual-dispatch trigger.
It downloads historical data, writes research artifacts, and retains them for
14 days. It has read-only repository permission, requires no API secret, never
calls a broker, and does not run on a schedule.

Before enabling a schedule, run at least several manual studies across distinct
periods and universes, review coverage and data-provider behaviour, then make a
separate decision about rate limits and artifact retention.

## n8n template

`automation/n8n/tradingagents-research-review.disabled.json` is a disabled,
manual-trigger review template. It contains no credentials, webhook, schedule,
or outbound notification node. Importing it into n8n leaves it inactive and it
will not run until an operator deliberately activates it.

To add a delivery channel later, create a new credential in n8n itself, append
an email/Telegram/Feishu/Slack node, and keep the workflow disabled until a
manual test confirms the message shows source, date range, coverage, cost
assumptions, and research-only disclaimer. Do not import credentials or alter
existing workflows from this repository.
