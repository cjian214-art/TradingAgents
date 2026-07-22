# OpenBB integration review — 2026-07-22

## Decision

OpenBB is **not added to this checkout or started as a service**. The current
research providers already cover the approved use cases: yfinance for US/HK
daily research and AKShare for China/Beijing daily research.

## Why it remains deferred

- The OpenBB repository currently identifies its licence as AGPLv3. Its own
  licence announcement says hosted or modified SaaS use needs source disclosure
  or a commercial licence. This project is deliberately Apache-licensed and
  may later expose reports through automation, so bundling it now would expand
  the licence review beyond the current research scope.
- OpenBB supports historical-price routes through provider extensions, but its
  documentation says endpoint/provider availability depends on the installed
  extensions and their provider-specific configuration. Adding it would not
  automatically improve data quality over the two explicitly validated
  providers.

## Revisit conditions

Revisit only if a required data source is unavailable through the existing
providers and an operator has selected the OpenBB provider, reviewed its data
licence/API key requirements, and decided whether the application will be
private/local or subject to AGPL/commercial-licence obligations.

Official references reviewed:

- https://github.com/OpenBB-finance/OpenBB
- https://openbb.co/blog/license-change-openbb-platform-goes-agpl/
- https://docs.openbb.co/odp/python/faqs/data_providers
- https://docs.openbb.co/odp/python/quickstart
