# B06 multi-GPU allocation validation

Owner approval: November 16, 2026, “Ok. I approved. GO ahead”.
Issue: https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/7
Baseline main: 56acad847d0575c8ef41646fe8127493349e4205 (PR #83).
Installed baseline: bef93c9e27ae6382695701e2e640852c78d79ab0 (PR #82).
Shared media contract remains 0.1.0; the new optional plan is private signed
operator authority, not a change to media records or public Studio dispatch.

## Approved scope

One fresh one-second trial, $5 total, $4 Pod reservation and $1 storage allowance,
1800 seconds from admission, one render, at most three allocation requests.
Hourly ceiling $4.50. One fixed provider name, deadline and reservation across
candidates. Only exact explicit HTTP 400 capacity rejection permits an untried
candidate; unknown response, cancellation, revocation, expiry or restart never
reposts. Signed plan permits the reviewed GPU types and up to eight locations per
GPU. Fresh connected quotes are checked before every POST. The candidate index
is saved before POST and retained with its result; backup validates this history.
The old expired unknown request and all five consumed scopes remain preserved.

## Worker compatibility review

The unchanged private digest is fce20324d1ae2f65f163f5550c7719d814f775468ce83475d4705f3f3bebed50.
It uses Python 3.11, PyTorch 2.8.0 / CUDA 12.8 and FlashAttention 2.8.3.
The exact pinned FlashAttention v2.8.3 README documents Ampere, Ada and Hopper,
including A100, RTX 4090 and H100, with BF16. Our inference requires BF16,
one CUDA GPU and pinned weights. These are supported architecture candidates;
this review does not establish that the binary or Wan execution has passed on
A100/H100. Actual device, output and memory measurements remain live evidence.
No Blackwell or AMD candidate is added. Keep CUDA >=12.8, host RAM >=64GB,
80GB ephemeral disk, Secure Cloud and no persistent volumes.

Source: https://github.com/Dao-AILab/flash-attention/blob/v2.8.3/README.md
Allocator reference: https://docs.runpod.io/api-reference-v2/pods/create-a-pod

## Validation and live result

Fictional verification: 197 root tests passed in 33.291s; 50 deployment,
guard, validation-policy and hosting tests passed in 1.504s. Contract, shell
syntax and whitespace checks passed. No new rental at this source checkpoint. Catalog availability is not a reservation and does not prove
all host RAM/disk constraints can be fulfilled. The control is application-side,
not a provider hard spending cap; actual hourly cost is checked after allocation.


## Live execution result — November 16, 2026

PR #84 is installed as 84fe9d2d9e2aad680c825069dd5dc5a84f5314f5. Upgrade
43976433823, preparation 43976625623 and admission 43976761613 passed.
The bound independent guard 43976858968 delivered READY before launch
43977423400 / job 133684894142.

The first POST allocated H100 80GB HBM3 Pod ymhk7srf23nend in CA-MTL-1 at
$4.39/hour. The frozen plan also included A100 SXM in EUR-IS-1; it was unavailable
at launch and no fallback was needed. Hardware inspection returned 81,559 MiB
and driver 595.91.07. The unchanged repaired worker completed successfully.
At 23:32:28 UTC the controller recorded one take, one worker attempt, one
allocation request, state succeeded and cleanup confirmed. Provider GET returned
404 and full inventory was empty. No further launch or render is authorized by
this consumed scope. The old exact unknown repair request remains unresolved.

| Observation | Result |
| --- | --- |
| Allocation | 23:13:54.118 UTC |
| Container start | 23:19:56 UTC |
| Pinned weights verified | 23:29:20.970 UTC |
| Worker completed | 23:32:20.224 UTC |
| Cleanup confirmed | 23:32:28.557 UTC |
| Sampling progress | 50/50 steps, about 25 seconds |
| Worker after weight verification | 179.254 seconds |
| Allocation through cleanup | 1114.416 seconds |
| Elapsed-time compute estimate | $1.36; not final billing |

The controller validated durable output before committing the take. Human creative
acceptance remains pending. Actual peak VRAM and exact model-load/generation
subdivisions were not retained; bounded read-only observers did not yield a
captured metric event before teardown. Future benchmarks must publish metrics to
durable controller storage before completing the take. Do not infer 4090 memory
fit from this H100 success. Final provider billing remains pending and the
reservation is retained. The independent guard continues through 23:44:46 UTC;
persistent cleanup continues afterward. See the evidence directory and master
handoff for the full identifiers, limits and remaining five-second work.
