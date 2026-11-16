# Draft for Runpod support — not sent

Subject: Confirm final outcome of one REST v2 Pod-create request

Please reconcile one POST https://api.runpod.io/v2/pods request in my account.

- Submitted: November 16, 2026, approximately 15:04:38 UTC.
- Origin: controller 64.225.114.46.
- Requested Pod name: `wan-534f9bd79f723ba2a85dc7a7df45c27f0946e30041ba06142d43130b28026648`.
- API key label: `wan-cleanup` (no key value is included).
- One Secure NVIDIA GeForce RTX 4090, EU-RO-1, minimum CUDA 12.8, minimum host RAM 64 GB, 80 GB ephemeral disk, no persistent/network volume and no queue option.
- The client submitted exactly one create. It lost the original HTTP status, response detail and request ID because of an error-handling defect that we have now corrected in source. We have not retried.
- No Pod ID, worker claim or video output was observed. Full inventory reads remained empty through the 15:33:20 UTC application deadline and the independent watch ending about 15:38:23 UTC. Later account inventory and audit reads were also empty. Pod billing for the trial window has no records yet; we are not treating that as final billing settlement.

Please provide the original final HTTP outcome and reason, confirm whether any allocation was created or remains pending for this exact request/name, and identify any associated Pod IDs or charges. If nothing was accepted, please explicitly confirm that this request cannot subsequently allocate a Pod, so we can safely close it before one new bounded attempt.

No credentials, private worker tokens, prompts, media or unrelated account records are attached.
