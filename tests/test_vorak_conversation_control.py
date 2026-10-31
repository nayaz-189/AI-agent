"""Offline tests for VORAK conversation stop, timed pause, and voice wiring.

Run: python -m unittest discover -s tests -p test_vorak_conversation_control.py -v
Does not open a microphone or connect to Gemini.
"""
from pathlib import Path
from unittest import TestCase

from vorak_integrated.conversation_control import ConversationGate, is_stop_utterance


class SpeechGateTests(TestCase):
    def test_stop_is_silent_until_a_new_user_turn(self):
        gate=ConversationGate()
        self.assertEqual(gate.stop()['status'],'speech_stopped')
        self.assertFalse(gate.should_play())
        self.assertFalse(gate.new_user_utterance('Stop'))
        self.assertFalse(gate.new_user_utterance('V, stop speaking.'))
        self.assertFalse(gate.should_play())
        self.assertTrue(gate.new_user_utterance('Explain Python lists to me'))
        self.assertTrue(gate.should_play())

    def test_stop_is_separate_from_pausing(self):
        gate=ConversationGate()
        gate.hold(10,now=100)
        self.assertEqual(gate.mode,'holding')
        gate.stop()
        self.assertEqual(gate.mode,'stopped')
        self.assertFalse(gate.is_current_hold(1,now=111))

    def test_pause_supports_only_exact_requested_windows(self):
        for seconds in (10,20,30):
            gate=ConversationGate()
            status=gate.hold(seconds,now=100.0)
            self.assertEqual(status['seconds'],seconds)
            self.assertFalse(gate.should_play())
            self.assertFalse(gate.is_current_hold(gate.generation,now=100+seconds-0.1))
            self.assertTrue(gate.is_current_hold(gate.generation,now=100+seconds))

    def test_pause_holds_through_second_question(self):
        gate=ConversationGate()
        gate.hold(20,now=1)
        self.assertFalse(gate.new_user_utterance('And how about the second question?'))
        self.assertEqual(gate.mode,'holding')

    def test_invalid_waits_do_not_change_state(self):
        gate=ConversationGate()
        for value in (0,5,11,40,-10,None,'10'):
            self.assertEqual(gate.hold(value)['status'],'invalid')
        self.assertTrue(gate.should_play())

    def test_old_timers_cannot_resume_after_new_pause(self):
        gate=ConversationGate()
        gate.hold(10,now=0)
        old=gate.generation
        gate.hold(30,now=2)
        self.assertFalse(gate.is_current_hold(old,now=100))
        self.assertTrue(gate.is_current_hold(gate.generation,now=32))

    def test_user_stop_variants(self):
        for phrase in ('stop', 'V stop', 'V, stop speaking.', 'Vorak, stop talking!', 'be quiet'):
            self.assertTrue(is_stop_utterance(phrase),phrase)
        for phrase in ('stop my coding task', 'stop processing payments', 'what is a stop word'):
            self.assertFalse(is_stop_utterance(phrase))

    def test_manual_continue(self):
        gate=ConversationGate()
        gate.hold(30,now=2)
        gate.resume()
        self.assertTrue(gate.should_play())
        self.assertFalse(gate.is_current_hold(1,now=40))

    def test_speech_stop_does_not_reference_task_cancellation(self):
        result=ConversationGate().stop()
        self.assertIn('No task was cancelled',result['message'])


class GeminiSchemaTests(TestCase):
    def test_gemini_live_tool_declarations_validate_without_connecting(self):
        from google.genai import types
        from vorak_integrated.live import TOOL
        config = types.LiveConnectConfig(tools=[TOOL])
        declaration = next(
            d for d in config.tools[0].function_declarations
            if d.name == 'conversation_control'
        )
        seconds = declaration.parameters.properties['seconds']
        self.assertEqual(seconds.type.value if hasattr(seconds.type, 'value') else str(seconds.type), 'STRING')
        self.assertEqual(seconds.enum, ['10', '20', '30'])


class LiveWiringTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(Path(__file__).resolve().parents[1]/
                    'vorak_integrated'/'live.py').read_text(encoding='utf-8')

    def test_existing_gemini_live_session_preserved(self):
        self.assertIn("async with client.aio.live.connect",self.source)
        self.assertIn("'name':'conversation_control'",self.source)
        self.assertIn("elif fc.name=='conversation_control':",self.source)
        self.assertIn("elif fc.name=='current_information':",self.source)
        self.assertIn("NO_INTERRUPTION",self.source)

    def test_headset_barge_in_does_not_block_in_audio_drain(self):
        self.assertIn("async def begin_background_drain():",self.source)
        self.assertIn("if barge_in:\n                                await begin_background_drain()",self.source)
        self.assertIn("await interrupt_draining()",self.source)
        self.assertIn("finish_spoken_answer(interrupted=True)",self.source)

    def test_pause_timer_and_task_separation(self):
        self.assertIn("resume_after_hold(gate.generation,seconds)",self.source)
        self.assertIn("'status':'speech_paused'",self.source)
        self.assertIn("if gate.mode=='holding' and fc.name!='conversation_control':",self.source)
