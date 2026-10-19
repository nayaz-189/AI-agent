# Day 18 recovery checkpoint

Updated 2026-10-19. Branch `feature/day18-voice`, baseline `bae5db4`.
Implementation is **partial: physical owner acceptance failed**. Checkpoint scope
is this partial implementation; use Git log for its exact commit and publication state.
Live voice actions are disabled by fixed `VOICE_ACTIONS_READY = False`; this is not
a configuration option. Do not enable it without reviewed successful physical tests.

## Preserved work

Do not reset/stash/delete existing changes. Preserve the unrelated Day 17 patch
files, `execution/device_client.py.day17-backup` and `execution/usb_demo.py`.
Day 17 device authentication, protocol and replay implementation remain unchanged.

## Implemented

`voice/`: explicit bounded capture/playback, local STT/TTS, experimental ECAPA
identity enrollment/calibration, closed settings, bounded local conversation,
CLI and composition through the existing planner/validator/runtime. Native
confirmation remains mandatory in the routed action path. Only Calculator is
implemented, and current live readiness policy blocks it. Text/phone paths are unchanged.
Identity warmup precedes fresh recordings. Model downloads use pinned public
hashes; inference never downloads. Source indexing includes only flat voice source.

## Executed checks so far

- `pip check`: no broken requirements.
- Audio tests: 14 passed, synthetic/mocked.
- Dialogue tests: 16 passed, synthetic/mocked.
- Identity tests: 21 passed, synthetic/mocked.
- Runtime tests: 18 passed, including fixed live readiness denial.
- Storage/setup tests: 12 passed, confined synthetic fixtures.
- Validator: 6 passed. Source/export security: 17 passed.
- Final complete regression suite passed after readiness denial: 313 cases, zero
  failures or harness skips (287 top-level functions + 17 source tests + three
  legacy executor scenarios + six validator cases). 81 voice tests are included.
  An execution audit confirmed the original 285 functions actually ran; two later
  added functions also passed explicitly and through the final suite.
- Final compilation, dependency check, source checks and staged whitespace check
  passed. Existing text-mode start/exit passed. Day 17 device tests: 37 passed;
  physical Android was not retested. Exactly 23 Day 18 files are reviewed for Git.
- Real ECAPA inference on a synthetic waveform: cold load + inference 14.983 s.
- Quantized Kokoro failed with unsupported CPU ConvInteger node. Replaced manifest
  with official full-precision `kokoro-v1.0.onnx`; original ignored file preserved.
- Full-precision Kokoro and other downloaded assets have passed SHA-256 checks.
  Full-precision model loaded in 4.138 s. Real synthesis succeeded: male first
  utterance 9926.71 ms; female 1575.82 ms. Faster Whisper loaded in 12.262 s and
  transcribed the generated "Open Calculator" correctly in 682.24 ms.
- Latest free memory before inference: approximately 2.8 GiB. Check again before
  physical model loading; never terminate user processes automatically.

## Physical acceptance pending

Owner has confirmed availability, a second consenting speaker, and memory cleanup.
Do not ask availability again. Initial capture failed with a generic error; added
closed audio errors and a model-free `microphone-test` command. User then reported
microphone success, owner enrollment success and separate calibration success.
Artifact presence and Git exclusion were checked without reading biometric data.
Fresh owner and second-speaker tests BOTH returned OWNER_UNCERTAIN (1367.46 ms,
1374.2 ms); neither authorizes actions. No threshold was weakened. Added a safe
`reason` label to distinguish a score in the uncertainty band from unavailable
verification. Subsequent results are below. No replay or spoken Calculator success
is claimed.

Latest physical update: user confirmed BOTH neural previews were audible and
natural. Separate calibration succeeded. Additional fresh non-owner and owner
recordings both returned OWNER_REJECTED with `reason=similarity_evaluated`
(1901.46 ms and 1768.22 ms). User confirmed enrollment/calibration speaker order
and microphone setup were correct. This is a real failed owner-acceptance test,
not a backend-load error. Keep cutoff unchanged and do not claim the milestone
complete. Upstream feature/normalization/ECAPA configuration was compared and
matches. Generated-speech tests accepted a new same-voice long sentence, marked its
short Calculator command uncertain and rejected a different voice. Speech-region
preprocessing did not fix that uncertainty, so it was NOT added to production.
No owner audio was retained. Both previews were confirmed audible and natural.
Real local Ollama public-question inference passed in 12858.04 ms with one context
turn. Do not claim a physically verified voice conversation from that separate test.

## Next steps

1. Owner-profile generalization is a real unresolved acceptance blocker. Preserve
   artifacts; future evaluation needs more independent samples and quality analysis.
   Do not lower cutoffs, keep retrying until a lucky pass, or bypass native consent.
2. Final tests/compilation passed. Review the exact staged diff and publication state.
3. Checkpoint partial implementation safely; no more physical recordings needed
   for the current failed-acceptance conclusion.
4. Update existing `docs/day18-voice.md` and dependency declarations with final results.
5. Full suite, device tests, validator, source tests, compilation, whitespace and
   staged privacy review. Stage exact Day 18 paths only.
6. User authorizes a safe feature-branch commit and non-forced push, including a
   clearly labeled partial checkpoint if physical acceptance is unresolved.
   Never merge main, finalize or change lifecycle records.

## Useful commands

```powershell
.\.venv\Scripts\python.exe -m voice.cli status
.\.venv\Scripts\python.exe -m voice.cli enroll
.\.venv\Scripts\python.exe -m voice.cli calibrate
.\.venv\Scripts\python.exe -m voice.cli preview --voice male
.\.venv\Scripts\python.exe -m voice.cli preview --voice female
.\.venv\Scripts\python.exe -m voice.cli verify
.\.venv\Scripts\python.exe main.py --voice listen --once
.\.venv\Scripts\python.exe -m execution.regression_suite
.\.venv\Scripts\python.exe -m execution.test_device_protocol
.\.venv\Scripts\python.exe -m brain.validator
.\.venv\Scripts\python.exe -m knowledge.test_source_security
```

No genuine acoustic wake detector or anti-spoof/liveness proof exists. Voice
similarity plus native consent does not isolate the process from same-user malware.
