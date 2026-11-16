# Isolated validation authorized while support reconciles the old request

Owner instruction: “we do not need to wait. we can make a new test in the mean time”.
This authorizes one fresh isolated one-second test and its necessary deployment,
using the existing $5 total / 1800 seconds / one create / one render envelope.
The exact historical unknown request retains its cleanup obligation and $4 reservation.
The persistent cleanup process stays alive across the source upgrade. The separate
new deadline guard also deletes any late allocation for the old exact request.

Baseline: 532f1025beba94b9a4218a1cab19d0c826fed3a2. Installed before upgrade: 42b3e993.
Contract: 0.1.0. No new Pod or runtime authority at this implementation checkpoint.

Verification on fictional data:
- 172 root tests passed in 34.261 seconds.
- 46 deployment, guard, hosting and exact historical-exception tests passed in 2.518 seconds.
- Contract validation, shell syntax and git diff whitespace checks passed.
- Normal backup/restore eligibility is unchanged. The private maintenance checkpoint
  preserves the unresolved record and is not an automatically restorable bundle.

Live deployment, run IDs, output and cleanup result will be appended after execution.
