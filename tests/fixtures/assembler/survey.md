# Repository Survey: acme-payments

**Generated**: 2026-01-01T00:00:00+00:00

## Purpose & Context

acme-payments is a payment settlement service that captures authorized card
charges and reconciles them into per-merchant payouts. It exposes an internal
API consumed by merchant backends and emits ledger events for downstream
accounting systems.

## Key Files

| Path | Why it matters |
|---|---|
| `src/services/capture.py` | Core capture operation and idempotency guard |
| `src/domain/ledger.py` | Double-entry ledger invariants |
| `src/api/server.py` | API surface entry point |
