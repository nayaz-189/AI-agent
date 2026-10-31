"""Offline contract checks for experimental headset interruption.

Run: python -m unittest discover -s tests -p test_vorak_barge_in.py -v
No microphone, network or speaker hardware required.
"""
from pathlib import Path
from unittest import TestCase

from vorak_integrated.stability import AudioSink


class AudioAbortTests(TestCase):
    def test_abort_discards_unplayed_pcm(self):
        sink = AudioSink(sounddevice=None)
        sink.write(b"\x00\x00" * 400)
        sink.write(b"\x01\x00" * 400)
        self.assertGreater(sink.q.unfinished_tasks, 0)
        sink.abort()
        self.assertTrue(sink.stop.is_set())
        self.assertEqual(sink.q.unfinished_tasks, 0)

    def test_abort_idempotent(self):
        sink = AudioSink(sounddevice=None)
        sink.abort()
        sink.abort()
        self.assertTrue(sink.stop.is_set())


class ConfigTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (Path(__file__).resolve().parents[1] /
                      "vorak_integrated" / "live.py").read_text(encoding="utf-8")

    def test_barge_in_opt_in_only(self):
        self.assertIn("p.add_argument('--barge-in',action='store_true'", self.source)
        self.assertIn("if args.barge_in and args.audio_mode != 'headset':", self.source)
        self.assertIn("START_OF_ACTIVITY_INTERRUPTS", self.source)
        self.assertIn("if barge_in else {'activity_handling': types.ActivityHandling.NO_INTERRUPTION}", self.source)

    def test_false_activation_protection(self):
        self.assertIn("START_SENSITIVITY_LOW", self.source)
        self.assertIn("'silence_duration_ms': 1450", self.source)
        self.assertIn("if not barge_in:", self.source)

    def test_interruption_clears_old_speech(self):
        self.assertIn("output.abort()", self.source)
        self.assertIn("finish_spoken_answer(interrupted=True)", self.source)

    def test_original_voice_and_research_remain(self):
        self.assertIn("async with client.aio.live.connect", self.source)
        self.assertIn("AudioGuard(mode=args.audio_mode", self.source)
        self.assertIn("elif fc.name=='expert_research':", self.source)
        self.assertIn("elif fc.name=='current_information':", self.source)
