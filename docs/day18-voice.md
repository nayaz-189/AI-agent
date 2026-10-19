# Day 18: local owner-verified voice prototype

Status: **partial; live voice actions disabled after failed physical owner acceptance**.
The implementation extends Day 17 baseline `bae5db4` on `feature/day18-voice`.
Text mode and authenticated device transport remain independent existing interfaces.
`VOICE_ACTIONS_READY` is a fixed false runtime policy, not a setting or environment
override. The routed path is tested synthetically but must remain disabled until
a reviewed physical acceptance test succeeds.

## How it works

1. Start the local CLI and explicitly press Enter before each six-second recording.
2. The microphone produces mono 16 kHz float32 samples in memory. Level, clipping,
   duration and format checks reject unusable input. Capture and playback cannot
   overlap within the process.
3. A warmed SpeechBrain ECAPA model compares a fresh recording with the private
   owner profile. Rejected, uncertain, stale and unavailable results stop the request
   before transcription. Every recording needs its own verification.
4. Faster Whisper transcribes locally. Transcript-based wake phrases or explicit
   push-to-talk activate a bounded conversation session. This is **not acoustic
   always-on wake-word detection**; no microphone opens on ordinary startup.
5. Conservative whole-command matching identifies an explicit Calculator request.
   Negation, hypotheses, quotations and additional actions do not match. Other
   conversation goes only to the existing loopback Ollama client, with no tools.
6. The existing planner converts the canonical request to a plan; its normal fast
   router handles Calculator. The existing validator must accept exactly
   `open_calculator` with empty arguments. No new execution engine is introduced.
   The current readiness denial blocks live voice actions before this step.
7. A real Windows permission dialog asks about the exact action, session and capture.
   A trusted `ConfirmationAuthority` token lasts 15 seconds and is consumed once.
   The recording must still be at most 30 seconds old after confirmation. Spoken
   "yes", planner flags, a previous session and model output grant no authority.
8. The existing `execution.runtime`, TaskExecutor, ExecutionRouter, registry and
   desktop gates execute the request. Independent Calculator observation records
   a task-bound receipt. Completion is spoken only if that receipt validates.
9. Kokoro generates the response with the selected male/female voice. Esc cancels
   recording or playback; Ctrl+C exits. Cancelling cannot undo an executed action.

## Stack and private files

| Component | Selection and reason |
| --- | --- |
| Audio | sounddevice 0.5.6 / NumPy 2.2.6; bounded in-memory PortAudio streams |
| Recognition | faster-whisper 1.2.1 / CTranslate2 4.8.3; tiny.en, CPU int8, two threads |
| Speaker similarity | SpeechBrain 1.0.3; ECAPA VoxCeleb, 192-dimensional embeddings; CPU PyTorch/TorchAudio 2.8.0 |
| Speech | kokoro-onnx 0.6.1 / ONNX Runtime 1.23.2; official full-precision v1.0 graph |
| Voices | Actual installed asset identifiers `am_michael` and `af_sarah` |
| Conversation | Existing local `qwen3:0.6b` role via Ollama at `127.0.0.1:11434`; proxies and redirects disabled |

Optional package versions are declared in `requirements-voice.txt`. Models are
downloaded separately, only by an explicit setup command. `voice/models.py` holds
exact public URLs, revisions, byte counts and SHA-256 digests. Inference checks
integrity, refuses redirected paths and never downloads remote Python/YAML.

Sources: [Faster Whisper](https://github.com/SYSTRAN/faster-whisper),
[pinned tiny.en weights](https://huggingface.co/Systran/faster-whisper-tiny.en/tree/0d3d19a32d3338f10357c0889762bd8d64bbdeba),
[pinned ECAPA weights](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb/tree/1e47a43813bfa3dfebda84fca9620394f74cc55a),
[official Kokoro release](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1).

The full-precision Kokoro graph is 325,505,369 bytes with SHA-256
`beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a`.
The earlier quantized graph failed on this Windows CPU runtime with unsupported
`ConvInteger`; it is no longer selected. Its existing ignored cache was preserved.

Private storage is under `runtime/voice/`, excluded from Git and source indexing:

- `models/`: public model weights, about 0.49 GiB for the active model set.
- `identity/enrollment.json`: owner centroid and sample digests, no recording.
- `identity/calibration.json`: empirical score cutoffs bound to the exact profile.
- `settings.json`: voice, style, profanity, rate, volume, timeout and device choices.

Windows storage reuses the existing owner/SYSTEM ACL and exclusive-create helpers.
Enrollment/calibration refuse replacement. There is deliberately no automatic reset
or re-enrollment command. Never delete an existing profile simply to make a test pass.

## Setup on Windows

Use the existing Python 3.10 virtual environment. The current development machine
already has these dependencies and models; do not reinstall or redownload them.
For a fresh environment, install only after its owner authorizes package changes:

```powershell
cd C:\AI-agent
.\.venv\Scripts\python.exe -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements-voice.txt
.\.venv\Scripts\python.exe -m voice.cli models
.\.venv\Scripts\python.exe -m voice.cli status
```

Allow microphone access for desktop apps in Windows settings yourself if needed.
The CLI checks at least 2 GiB free RAM before neural startup. This is a minimum
preflight, not a memory reservation; close unused apps yourself if memory is tight.
No user processes are terminated or models unloaded by setup.

```powershell
.\.venv\Scripts\python.exe -m voice.cli devices
.\.venv\Scripts\python.exe -m voice.cli microphone-test
# Optional: choose IDs shown by devices. Never use a speaker-loopback input.
.\.venv\Scripts\python.exe -m voice.cli settings --input-device 1 --output-device 3
```

Device IDs are machine-specific. Input must support mono 16 kHz; unsupported
formats fail rather than silently relabelling samples. `microphone-test` loads no
speech model, saves no audio and does not claim identity or speech recognition.

## Enrollment and calibration

```powershell
.\.venv\Scripts\python.exe -m voice.cli enroll
.\.venv\Scripts\python.exe -m voice.cli calibrate
```

Wait for warmup, press Enter before each phrase, and speak while LISTENING is shown.
Enrollment requires three distinct, intelligible phrases and native confirmation.
Calibration requires two new owner samples and two distinct samples from a different
consenting adult, followed by native confirmation. No transcript or raw audio is saved.
Calibration alone does not enable voice actions: later owner acceptance failed.
Preserve the current enrollment and calibration artifacts for an authorized follow-up.

Embeddings are unit-normalized; the owner centroid is the normalized enrollment
mean. Similarity is their dot product (cosine similarity). Acceptance requires at
least the lowest held-out owner score. Rejection occurs at or below the highest
non-owner score; scores between them are uncertain. Overlapping calibration fails.
These small-sample empirical cutoffs are not statistically validated false-accept
rates and do not establish liveness, uniqueness or resistance to voice cloning.

## Voices, personality and normal use

```powershell
.\.venv\Scripts\python.exe -m voice.cli preview --voice male
.\.venv\Scripts\python.exe -m voice.cli preview --voice female
.\.venv\Scripts\python.exe -m voice.cli settings --voice female --rate 1.0 --volume 0.8
.\.venv\Scripts\python.exe -m voice.cli settings --style adaptive --profanity natural
.\.venv\Scripts\python.exe main.py --voice
# Single-request pipeline; Calculator remains blocked by readiness policy:
.\.venv\Scripts\python.exe main.py --voice listen --once
# Existing text mode:
.\.venv\Scripts\python.exe main.py
```

The intended command is **"Yo Vorak, pull up Calculator."** after pressing Enter.
Currently no Calculator action or permission dialog is allowed from voice mode.
Once physical readiness is reviewed and enabled, the exact-action Windows dialog
is still required. **"Open Calculator"** also matches under PTT; matching grants no authority.
Supported wake phrases include Hey/Yo/Alright Vorak, Wake up Vorak, Vorak you there,
Vorak listen up and What's up V. Generic casual greetings do not independently wake
an inactive session. Accent/proper-name recognition is not guaranteed by tiny.en.

Style choices are adaptive (default), playful, direct and professional. Profanity
choices are off, mild, natural (default) and strong; allowed language is contextual,
not mechanically inserted. Conversation uses at most eight turns/6000 characters
in memory and expires after 30 seconds by default. Every follow-up is a new explicit
recording and speaker check. Say "switch to the female voice" or "use the male voice"
to persist that preference without replacing the current conversation component.

Esc cancels audio; inference already running may finish before control returns.
There is no hard process deadline for native model inference or a stuck audio driver.
Ctrl+C exits the CLI. No silent cloud or system-voice fallback is used if local models
fail. Normal text mode remains available independently.

## Physical acceptance procedure

1. Complete enrollment and separate calibration.
2. Run `python -m voice.cli verify` for a fresh owner sentence, then for the second
   consenting speaker. It reports only OWNER_VERIFIED/REJECTED/UNCERTAIN and timing;
   it never executes actions.
3. Test both previews and assess audibility, naturalness and interruption yourself.
4. Run `listen --once` for the owner's Calculator request and for a non-owner request.
   The non-owner must not reach the permission dialog or execution.
5. Test a negative command such as "Don't open Calculator"; it must not execute.
6. If available, play an owner recording from a separate device during a freshly
   activated `verify` capture. Do not supply private audio to the coding agent.
   A match is a known replay vulnerability, not evidence of liveness. Native consent
   remains mandatory even when similarity passes.

## Verification record

Automated tests exercise real planner/router/gates with synthetic identity, dialog
and OS boundaries. They do not open physical devices or prove speaker recognition.

| Check executed | Result |
| --- | --- |
| `python -m pip check` | Passed, no dependency conflicts |
| `python -m execution.test_voice_audio` | 14 passed |
| `python -m execution.test_voice_dialogue` | 16 passed |
| `python -m execution.test_voice_identity` | 21 passed |
| `python -m execution.test_voice_runtime` | 18 passed; includes default-deny readiness policy |
| `python -m execution.test_voice_storage` | 12 passed |
| `python -m execution.regression_suite` | Passed: 313 cases across the fixed inventory and validator |
| `python -m execution.test_device_protocol` | 37 passed; no physical Android retest |
| `python -m brain.validator` | 6/6 passed |
| `python -m knowledge.test_source_security` | 17/17 passed |
| Project `compileall`, `git diff --check`, staged whitespace check | Passed |

Total: **313 passed, 0 failed, 0 harness skips**. This counts 287 registered
top-level test functions, 17 source/export tests, three legacy executor scenarios
and six validator cases. The 81 voice cases are included, not additional. An
execution audit confirmed the original 285 functions ran; the two later privacy
and readiness tests were separately executed and included in the final passing
suite. All live action integration tests use synthetic identity/UI/OS boundaries
and an explicit trusted test patch for readiness; production readiness stays false.
Text-mode start/exit also passed using `'exit' | .\.venv\Scripts\python.exe main.py`.

Measured locally on CPU, with no raw recording saved:

- ECAPA cold load plus synthetic inference: 14.983 seconds.
- Full-precision Kokoro load: 4.138 seconds.
- First male synthetic "Open Calculator" generation: 9,926.71 ms, 1.653 s audio.
- Subsequent female generation: 1,575.82 ms, 1.386 s audio.
- Faster Whisper cold load: 12.262 seconds; generated-speech recognition: 682.24 ms,
  correctly transcribed "Open calculator." This is genuine inference, not a mic test.
- Physical microphone test: owner reported format/level checks passed.
- Physical enrollment: owner reported profile creation succeeded after retry.
- Calibration: user reported completion; artifact presence and Git exclusion were
  checked without reading biometric contents.
- Fresh samples initially returned OWNER_UNCERTAIN. Later separate non-owner and
  owner recordings both returned OWNER_REJECTED with real similarity evaluation,
  taking 1901.46 ms and 1768.22 ms respectively. The user confirmed correct speaker
  order and consistent microphone setup during enrollment and calibration.
- **Owner acceptance failed.** The non-owner remained blocked. Cutoffs and profiles
  were not weakened or overwritten; live voice actions are now disabled.
- Both neural previews: user confirmed audible, natural-sounding male/female speech.
- Controlled generated-speech experiment: a fresh same-voice long sentence was
  accepted, its short Calculator command was uncertain, and a different voice was
  rejected. Detected speech regions did not resolve short-command uncertainty.
  This experiment accessed no real profile and changed no production preprocessing.
- Real loopback Ollama public-question test: valid reply in 12858.04 ms; one context
  turn retained. This tested local conversation, not a physically verified voice session.
- Replay testing, spoken Calculator verification and physical Android retest were
  not completed; no success is claimed for those checks.

The first physical enrollment attempt stopped during capture. A standalone microphone
test then passed and enrollment succeeded. The exact transient cause is unconfirmed;
the CLI now reports closed, specific audio errors instead of a generic setup failure.
SpeechBrain's file-backend warnings do not prevent the tested in-memory embedding
path. Adding codecs would not fix the demonstrated similarity rejection.

## Security limits and review points

- Speaker similarity is experimental and vulnerable to playback/synthesis. It is
  additional friction, never a substitute for Day 17 cryptographic authentication.
- The native consent dialog is a local application boundary, not Windows logon,
  an enclave or a protected desktop. Same-user malware can alter Python, inject UI,
  read memory or modify owner-owned files. No OS sandbox/broker was introduced.
- Raw audio remains in process memory only; this is not guaranteed secure erasure
  or protection against OS paging/crash dumps. Calibration digests are sensitive
  derived data and remain private. Do not commit or publish runtime storage.
- Model hashes protect expected assets; same-user changes between validation and
  backend path reopening are outside the process trust boundary.
- Energy checks are not robust background-noise/liveness detection. tiny.en can
  misrecognize accents, proper names or noise. Ambiguous results must stay blocked.
- Generated conversation is labeled and filtered, but a word filter cannot prove
  every semantic claim truthful. Only runtime receipts establish action completion.
- No browser/private-file tools, arbitrary shell, remote voice endpoint, continuous
  recording, external speech API or new device permissions were added.
- The standard regression inventory includes every new voice test; missing optional
  test dependencies fail the suite instead of silently skipping security checks.
- Finalizer/lifecycle allowlists and records remain unchanged. Day 18 docs, optional
  requirements and voice sources need exact reviewed finalizer classification during
  a later authorized lifecycle transition. Do not broadly allow unknown directories.

## Files and recovery

`voice/audio.py`, `speech.py`, `identity.py`, `dialogue.py`, `settings.py`, `models.py`,
`runtime.py`, `cli.py` and `__init__.py` compose the feature. Five
`execution/test_voice_*.py` modules cover it. Existing changes are limited to the
optional main entry point, bounded Ollama options, test inventory, source-index
allowlist/tests and `.gitignore`. Dependencies and this documentation are separate.

See `docs/day18-progress.md` for interruption recovery. Never reset the working tree,
overwrite enrollment, remove Day 17 patches, reinstall functioning packages or
reuse synthetic speaker results as evidence that physical acceptance passed.

Next work is a controlled investigation of owner-profile generalization across
phrases, durations and acoustic conditions, with larger independent calibration
and evaluation sets. Any preprocessing/profile-format change needs new explicitly
authorized enrollment while preserving current artifacts. Do not enable actions
or lower thresholds merely to obtain a successful demonstration.
