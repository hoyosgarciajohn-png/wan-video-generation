# B06 memory repair candidate — GPU validation pending

The November 16 one-second diagnostic failed with `gpu_out_of_memory`. No take was
saved. It reached a captured 39/50 sampling steps; the exact failing allocation and
whether sampling completed were not captured. Do not relabel the earlier five-second
failure as OOM: its cause remains unknown.

## Pinned-source findings

The worker used CPU T5 encoding and `offload_model=True`. Runtime observations showed
approximately ten minutes before GPU sampling, followed by about 1.54 seconds per
sampling step. This is not a complete profiler trace.

At upstream revision `e5058c08fada388b04bb3d1a4734bddbd2fdeac5`:

- [textimage2video.py](https://github.com/Wan-Video/Wan2.2/blob/e5058c08fada388b04bb3d1a4734bddbd2fdeac5/wan/textimage2video.py)
  initializes VAE without a dtype override; supports CPU-initialized DiT; and with
  GPU T5 plus offload enabled, moves T5 back to CPU before moving DiT to the GPU.
  It also offloads DiT before VAE decoding.
- [vae2_2.py](https://github.com/Wan-Video/Wan2.2/blob/e5058c08fada388b04bb3d1a4734bddbd2fdeac5/wan/modules/vae2_2.py)
  defaults to float32 and uses its own dtype for the decode autocast context.

High decode memory is a plausible explanation, not a proved failing stage. The
candidate addresses that risk and the observed preparation delay without changing
weights, resolution, frame count, solver, seed or sampling steps.

## Prepared changes

1. Construct with `init_on_cpu=True`, `t5_cpu=False` and `offload_model=True` so
   text encoding and DiT execution occupy the GPU sequentially.
2. Require BF16-capable CUDA and set both VAE parameters and its autocast dtype to
   BF16. This reduces memory demand but changes decoder arithmetic; output quality,
   finite values and actual GPU memory fit still require live validation.
3. Emit fixed phase labels for text encoding and video decoding. Preserve the safe
   phase in the terminal log and failure journal, including on CUDA OOM. API failure
   codes remain unchanged; prompts and raw exception messages remain private.
4. Record the memory policy in successful inference metrics.

Ten targeted CPU-only fictional checks passed, covering invocation configuration,
missing BF16 rejection, wrapper transparency, decoder-failure phase preservation,
private-log exclusion and consumed-attempt replay rejection. They do not demonstrate
upstream/CUDA compatibility, a successful video, or improved creative quality.

## Release boundary

This is a source candidate only: not built, published, installed or GPU-validated.
The installed worker image is still the diagnostic image ending `f993b`.
Changed worker sources invalidate its source-bound build evidence. Before another
trial, build and attest a new immutable private image, finish source review, and
prepare a fresh isolated runtime grant. Both earlier attempts are consumed.
No third Pod create or render is authorized. Do not reset either historical job,
change its deadline or reuse an existing grant. Keep current billing liabilities.

The next eligible paid validation would be one one-second shot, one create/render,
at most $5 additional and 1,800 seconds from its own admission, only after new owner
approval and verified image/guard readiness. This document grants no spending.
