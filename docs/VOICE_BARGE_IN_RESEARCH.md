# VORAK speech interruption — root cause, evidence and validation

Date: 2026-10-31. Status: **Windows live validation pending**.

## Proven failure in reported terminal run

The tested launch was `python -m vorak_integrated.live --profile alex --mic-device 1`.
That runs in default `speakers` mode with `barge_in=False`. The microphone callback
is disabled during playback and the Gemini config uses `NO_INTERRUPTION`.
Consequently saying "stop" over VORAK's speech is not captured. Changing the
LLM instruction alone cannot repair an unstreamed audio command.

## References inspected

- Gemini Live API capabilities and interruption handling:
  https://ai.google.dev/gemini-api/docs/live-api/capabilities
- Google Gemini Python Live example (explicitly says use headphones to avoid echo):
  https://github.com/google-gemini/cookbook/blob/main/quickstarts/Get_started_LiveAPI.py
- Google Gemini Live CLI example (clears playback on interrupt):
  https://github.com/google-gemini/gemini-live-api-examples/blob/main/command-line/python/main.py
- Google Live troubleshooting (audio streaming, playback flush and VAD):
  https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/live-api/troubleshooting
- LiveKit turn-handling docs (VAD vs adaptive interruption, false positives):
  https://docs.livekit.io/agents/logic/turns/adaptive-interruption-handling/
- Open source Windows AEC3 reference (requires acoustic render stream and OS-specific build):
  https://github.com/codejq/webrtc-aec
- Acoustic echo cancellation challenge research:
  https://arxiv.org/abs/2309.12553
- 2025 hands-free/full duplex AEC paper:
  https://arxiv.org/abs/2508.07561

## Scope of this patch

1. Preserve the existing Puck/Gemini Live system and existing policy restrictions.
2. Do not claim microphone voice interruptions work in default speaker mode.
3. Headphones + `--audio-mode headset --barge-in` keep streaming microphone
   audio and process Gemini interrupted events before new playback.
4. Ctrl+Alt+S is a Windows emergency **speech-only** stop fallback.
   It should work even if the default speaker-mode mic is muted.
5. Recognize explicit "pause/wait/give me 10,20,30 seconds" from accepted
   input transcripts, without requiring a model tool call.
6. Keep original timed pause when Gemini issues a duplicate pause function call.
7. No background task cancellation, no owner biometric threshold changes.

## Windows checks

```powershell
cd C:\AI-agent
.\.venv\Scripts\Activate.ps1
python -m py_compile .\vorak_integrated\live.py .\vorak_integrated\conversation_control.py
python -m unittest discover -s tests -p test_vorak_conversation_control.py -v
```

**Speaker mode:** Ask for a long answer. Press Ctrl+Alt+S. Audio should stop,
print `CONVERSATION: speech_stopped (Ctrl+Alt+S)`, and not automatically resume.
A spoken STOP in this mode remains unsupported.

**Headset mode:** Wear real headphones and launch:
```powershell
python -m vorak_integrated.live --profile alex --mic-device 1 --audio-mode headset --barge-in
```
Ask for a long answer and say "V, stop" while VORAK speaks. Test once from
near and once from a normal microphone distance. Observe if `YOU:` and
`CONVERSATION:` reflect the utterance. Do not assume success from unit tests.

**Pause mode:** With mic available, say "V, pause for 10 seconds. Explain AI",
add a distinct follow-up within the 10 seconds. Repeat with 20 and 30 seconds.
Verify no early speech, no stuck timer, and whether combined response actually
includes both questions.

## Still missing

Reliable hands-free **speakerphone** voice interruptions require proper AEC:
render-reference PCM, capture/render device clock alignment, adaptive echo
suppression, input VAD/ASR, then Gemini event handling. An arbitrary microphone
threshold is not a substitute for echo cancellation. This has not been
implemented or validated on the user's Windows hardware. Exact merging of
separate voice turns into one response is also experimental.
