import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from voice_session import VoiceSession, VoiceState


class VoiceSessionTests(unittest.TestCase):
    def session(self):
        temp = tempfile.TemporaryDirectory()
        return temp, VoiceSession(Path(temp.name), profile="natural", device=1)

    def test_session_is_persisted(self):
        temp, session = self.session()
        try:
            self.assertTrue(session.path.exists())
            payload = json.loads(session.path.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "idle")
        finally:
            temp.cleanup()

    def test_valid_conversation_cycle(self):
        temp, session = self.session()
        try:
            session.transition(VoiceState.LISTENING)
            session.transition(VoiceState.TRANSCRIBING)
            session.transition(VoiceState.THINKING)
            session.transition(VoiceState.SPEAKING)
            session.add_turn("Ola", "Ola, Kaua.", 1, {"accepted": True}, "conv-1")
            session.transition(VoiceState.LISTENING)
            self.assertEqual(session.conversation_id, "conv-1")
            self.assertEqual(len(session.turns), 1)
            self.assertEqual(session.state, VoiceState.LISTENING)
        finally:
            temp.cleanup()

    def test_invalid_transition_is_rejected(self):
        temp, session = self.session()
        try:
            with self.assertRaises(ValueError):
                session.transition(VoiceState.SPEAKING)
        finally:
            temp.cleanup()

    def test_error_can_recover(self):
        temp, session = self.session()
        try:
            session.transition(VoiceState.LISTENING)
            session.register_error("temporary failure")
            self.assertEqual(session.state, VoiceState.ERROR)
            session.recover()
            self.assertEqual(session.state, VoiceState.LISTENING)
        finally:
            temp.cleanup()

    def test_silence_is_counted_without_losing_session(self):
        temp, session = self.session()
        try:
            session.transition(VoiceState.LISTENING)
            session.register_silence()
            self.assertEqual(session.silence_timeouts, 1)
            self.assertEqual(session.state, VoiceState.LISTENING)
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
