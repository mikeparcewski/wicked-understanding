# Domain Model: acme-payments

**Generated**: 2026-01-01T00:00:00+00:00

## Domain Summary

acme-payments settles card transactions for online merchants. The core job is
turning an authorized charge into a captured, reconciled ledger entry while
enforcing idempotency and per-merchant payout rules.

## Core Entities

### Charge
- **Represents**: a single attempt to move money from a customer to a merchant
- **Key attributes**: `id`, `amount_cents`, `currency`, `status`
- **Lifecycle / States**: `authorized → captured → settled`
- **Relationships**: belongs-to Merchant, has-many LedgerEntry
- **File**: `src/domain/charge.py`

### Merchant
- **Represents**: a business that accepts payments through the platform
- **Key attributes**: `id`, `payout_schedule`, `mcc`
- **Lifecycle / States**: `pending → active → suspended`
- **Relationships**: has-many Charge
- **File**: `src/domain/merchant.py`

### LedgerEntry
- **Represents**: an immutable double-entry bookkeeping record
- **Key attributes**: `id`, `debit_cents`, `credit_cents`, `charge_id`
- **Lifecycle / States**: none (append-only)
- **Relationships**: belongs-to Charge
- **File**: `src/domain/ledger.py`

## Core Operations

### CaptureCharge
- **Trigger**: API call from merchant backend
- **Actor**: merchant integration
- **Inputs**: `charge_id`, `amount_cents`
- **Business rules**: capture amount must not exceed authorized amount
- **Side effects**: writes LedgerEntry, emits `charge.captured`
- **File**: `src/services/capture.py`

## Domain Rules & Invariants

Constraints enforced in code:
- A charge can be captured at most once — `src/services/capture.py:42`
- Ledger debits and credits must balance per charge — `src/domain/ledger.py:88`

## External Integrations

| Service | Purpose | Direction | File |
|---|---|---|---|
| CardNetwork | Authorization | outbound | `src/integrations/network.py` |

## Domain Glossary

| Term | Definition in this codebase |
|---|---|
| Capture | Finalizing an authorized charge so funds move |
| Settlement | Reconciling captured charges into a payout |
