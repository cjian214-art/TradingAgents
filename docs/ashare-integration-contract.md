# TradingAgents-AShare integration boundary

TradingAgents-AShare is a separate application. Its new API/frontend modules
and deep core modifications are under PolyForm Noncommercial 1.0.0; this
Apache-licensed TradingAgents checkout does not copy, import, bundle, or modify
that source.

## Local service configuration

The included Compose file is an example only. It uses a named `ashare` profile,
binds the application to `127.0.0.1:8010`, keeps its SQLite data in
`deploy/ashare/data`, and refuses to start without an operator-provided
`TA_APP_SECRET_KEY` in `deploy/ashare/.env`.

No command in this project starts the profile. If an operator decides to do so,
they must first review the upstream licence and service documentation, create
the secret, and run Compose manually from that directory.

## Version 1.0 REST contract

The local adapter builds, but does not send, this request:

```json
{
  "contract_version": "1.0",
  "method": "POST",
  "path": "/v1/analyze",
  "payload": {"symbol": "600519.SH", "trade_date": "2026-07-22"}
}
```

The expected acknowledgement contains a `job_id`. An eventual transport client
would then poll `GET /v1/jobs/{job_id}` and retrieve
`GET /v1/jobs/{job_id}/result`.

Only the target symbol and requested historical date cross the boundary.
Scanner rankings, local research-context files, user portfolios, credentials,
and n8n data do not cross it. Any future remote transport must be opt-in and
must require an operator-managed API token.
