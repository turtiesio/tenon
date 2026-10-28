# FPLE domain in Tenon

A contained, executable commerce domain extracted from `~/dev/fple`
at `f1e1b93bdb`. It has no dependencies, provider names, database code, HTTP,
environment reads, clocks, or filesystem access. The existing FPLE application
is unchanged.

`src/fple.tn` owns the public vocabulary, private aggregate state, authorization
and business transitions. Small private handlers own individual policies.
`src/fple_math.tn` owns checked integer arithmetic, cumulative allocation and
interval union. Keeping aggregate mutation in one Tenon module makes its
privacy boundary enforceable without exposing internal setters.

## Allowed actions

`Domain` is unique and its fields are private. Read models are copies.
`Request` is a closed set of proposals; it cannot mutate the aggregate.
Only an opaque `Action` returned by `allow` or `allowed` can be committed.
Its constructor, credentials and fields are private, and Tenon's codec cannot
forge it.

```tenon
import fple

fn perform(domain: mut fple.Domain, session: Str, key: Str,
           request: fple.Request, now: Int) -> Result[fple.Receipt, fple.Error] {
    let action = fple.allow(domain, session, key, request, now)?
    domain.commit(action, now)
}
```

Create a domain with `fple.Domain.new(scope, resolve)`. The host supplies
`resolve: fn(Str) -> Option[fple.Principal]`; it authenticates an opaque session
and returns its current subject and role. Roles are platform administrator,
seller scoped to one shop, buyer scoped to their own identity, and trusted
service. Constructors and the resolver are host trust boundaries. A client
must never supply its own principal or resolver to an existing domain.

`fple.allowed(domain, session, proposals, now)` returns only the individually
admitted actions from concrete `(idempotency_key, Request)` proposals. Use
`allow` to obtain a rejection reason for a particular proposal. Availability
and execution use the same reducer. No parallel transition table can drift.

Commit authenticates again, binds the action to its scope and principal,
checks its revision, and re-evaluates every policy with the current host time.
An intervening commit returns `Stale`; request fresh actions. Actions offered
together describe the same revision and are not a batch transaction.
Failures leave all aggregate state unchanged. An exact retry returns the
original receipt; reusing its key for different input or authority fails.

The entry module also exposes scoped `order`, `sku`, `customer`, `claim`,
`attempt`, `usage_seconds` and `settlement` reads. Public DTO constructors do
not grant write access to the aggregate.

## Domain rules

- Shops and customers must be active to buy or enter a broadcast. Seller
  mutations and financial reads are tenant scoped; buyers read their own
  orders, claims and point balances. Sellers manage customer blocks and grades.
- SKU zero prices inherit product prices. Stock respects auction and
  first-order holds. Holds can be reserved and released explicitly. A customer's
  product limit spans SKUs and previous active orders; completed removals
  release units from that limit.
- Following awards seller-scoped signup points once, including zero rewards.
  Checkout snapshots prices, discounts, shipping and cash/point allocation.
  Coupon ownership, activation, minimum spend, cap, expiry and single use are
  checked. Zero cash settles without a provider; card payments require 100 KRW.
- Unpaid cancellation restores stock, points and the reserved coupon atomically.
  Paid whole-order cancellation also restores shipping tender. Only redeemed
  attendance coupons are restored; other redeemed campaign coupons stay spent.
- Payment and refund preparations create stable attempt identities and effect
  descriptions. In-flight and unknown outcomes block another attempt. Only a
  definitive decline permits retry. Final outcomes are immutable, and approval
  evidence cannot be reused across attempts.
- Paid orders can be assigned, packed, invoiced, shipped and delivered.
  Tracking placeholders are rejected. Confirmation requires delivery, remaining
  units and no open claim; it closes subsequent claim and shipment mutations.
- Cancel, return and exchange have distinct forward stage sequences. Claim
  quantities exclude already removed or reserved units. Rejection, re-request
  and return withdrawal are explicit. Exchanges do not refund or restock.
  Cancel/return completion restores units and points exactly once and creates
  a cash liability that requires a separate refund attempt.
- Tender and quantity allocations are cumulative, conserving every won over
  partial refunds. Settlement uses actual approved cash and confirmed refunds;
  unresolved attempts fail the read. Fee returns use the original cumulative
  basis rather than rounding the remaining balance again.
- Broadcasts start as drafts and have explicit schedule/start/end/cancel/delete
  actions. Staff retain admission; customer and grade exclusions precede secret
  invitations. Secret admission can also use grade or received-cash criteria.
  Media issuance records no usage and requires no tariff.
- Provider usage can arrive after a broadcast ends and without an issuance
  record. Known project/channel/identity intervals are unioned per role;
  distinct unknown receipts remain distinct. Usage reads clip to caller-supplied
  windows and never read pricing or multiply by audience count.

Money is integer KRW. Times and usage intervals are integer epoch seconds;
intervals are half open. The host supplies authoritative current time and KST
day boundaries. Overflow and invalid arithmetic return errors. There are no
floating-point financial calculations.

## Host integration and recovery

`Charge`, `AwaitDeposit`, `Refund` and `MediaAccess` are descriptions, not I/O.
The host binds payment providers, deposit verification and media transport.
Trusted service/platform observations must verify the attempt's actual amount,
currency and final external evidence. Evidence strings must identify the
particular provider operation, including distinct refund operations.

Receipts include scope, revision, key, historical principal, time, request and
effects. A host durably records each new revision once, before performing its
external effects. Stable attempt identities are provider idempotency keys.
Returning an old receipt does not authorize repeating a charge or issuing a
fresh transport credential.

`Domain.restore(scope, resolve, history, verify)` reconstructs private state
from a contiguous log. The host's `verify: fn(Receipt) -> Bool` authenticates
historical records for that scope. Replay rechecks business rules, revisions,
keys and effect consistency, and executes no external effects. Historical
authority does not revive a revoked current login. In-flight/unknown attempts,
stock reservations, point balances and retry receipts survive reconstruction.

Atomicity here is in memory. The host owns durable append, optimistic revision
checks or transaction locks, and crash recovery. If persistence fails, discard
the candidate domain and restore the durable log before serving another
request. After a crash around provider I/O, reconcile the saved attempt rather
than submit it again. The package supplies no storage or transport adapter.

## Extraction scope and source mapping

Source paths below are relative to `~/dev/fple/packages/commerce/src`:

- Catalog: `verticals/catalog/domain/{sku-price,sku-hold,product-discount,product-order-limit}.ts`.
- Customer: `verticals/customer/domain/customer-policy.ts` and
  `verticals/customer/application/customer.service.ts`.
- Benefits: `verticals/benefits/domain/{point-policy,coupon-quote,discount-coupon-rules}.ts`
  and `verticals/benefits/README.md` for signup and cancellation restoration.
- Order: `verticals/order/domain/{checkout-money,checkout-point-policy,order-confirmation-policy,refund-allocation}.ts`.
- Payment: `verticals/payment/domain/{checkout-tender-policy,refund-policy}.ts`,
  `verticals/settlement/domain/platform-fee/charge-policy.ts` and the financial
  attempt/reconciliation invariants in `verticals/settlement/README.md`.
- Fulfillment: `verticals/fulfillment/domain/shipment-policy.ts` and `shipment.ts`.
- Claim: `verticals/claim/domain/{claim-stages,claim-policy}.ts`.
- Live: `verticals/live/domain/broadcast-lifecycle.ts`, `verticals/live/README.md`
  and `verticals/seller/domain/metered-usage.ts`.
- Settlement: `verticals/settlement/domain/settlement-policy.ts` for the
  KRW order-source 350/200 basis-point fees and cumulative fee returns.

This is a core domain definition, not TypeScript API or storage-format parity.
The scope is fully paid orders with one shipment per order, one SKU per claim,
fixed-expiry coupon grants, manual customer grades and all-time net received-cash
admission. It does not migrate existing FPLE records or implement partial item
payments, shipping groups, auctions, automatic monthly grades, campaign budgets,
guest admission, broadcast tariffs, FX, VAT, platform-fee adjustment/cash ledgers,
or FPLE's content, identity, notification and other peripheral workflows.
Those require their own explicit owner actions; no generic patch escape hatch
stands in for them.

## Verification

From the Tenon repository root:

```sh
apps/fple/test.sh
./check
```

The app harness tests an isolated package consumer using only a local dependency.
It runs scenarios on both the interpreter and C backend, plus compile rejection
tests for forged/decoded actions, private-state access, copied domains and
executing an unvalidated request. It includes exhaustive small-ratio arithmetic
and 64-bit boundaries, failed-transition rollback, tenant isolation, expiry
revalidation, cumulative refunds, recovery and metering. The harness owns its
temporary files and removes them on exit. `TENON=/absolute/path/to/tenon` selects
another compiler. Repository `./check` remains separate from the contained app
suite.
