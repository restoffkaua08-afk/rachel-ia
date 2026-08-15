import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from realtime_voice import AdaptiveVoiceDetector, BargeInConfig, monitor_process_for_barge_in


class FakeProcess:
    def __init__(self, cycles=20):
        self.cycles = cycles
        self.returncode = None
        self.terminated = False
    def poll(self):
        if self.terminated:
            return -15
        self.cycles -= 1
        if self.cycles <= 0:
            self.returncode = 0
        return self.returncode
    def terminate(self):
        self.terminated = True
        self.returncode = -15
    def kill(self):
        self.terminate()
    def wait(self, timeout=None):
        return self.returncode


class FakeStream:
    def __init__(self, values):
        self.values = iter(values)
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, blocksize): return next(self.values, 0.0), False


class RealtimeVoiceTests(unittest.TestCase):
    def config(self):
        return BargeInConfig(block_seconds=0.05, warmup_seconds=0.10, absolute_threshold=0.02, noise_multiplier=2.0, consecutive_blocks=3)

    def test_short_peak_does_not_interrupt(self):
        detector = AdaptiveVoiceDetector(self.config())
        values = [0.005, 0.005, 0.04, 0.005, 0.005]
        self.assertFalse(any(detector.observe_rms(value) for value in values))

    def test_sustained_voice_interrupts(self):
        detector = AdaptiveVoiceDetector(self.config())
        values = [0.005, 0.005, 0.04, 0.05, 0.06]
        self.assertTrue(any(detector.observe_rms(value) for value in values))

    def test_process_is_terminated_on_barge_in(self):
        process = FakeProcess()
        values = [0.005, 0.005, 0.05, 0.05, 0.05, 0.05]
        result = monitor_process_for_barge_in(
            process,
            None,
            self.config(),
            stream_factory=lambda **kwargs: FakeStream(values),
            rms_function=float,
        )
        self.assertTrue(result["interrupted"])
        self.assertTrue(process.terminated)

    def test_invalid_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            BargeInConfig(consecutive_blocks=0).validate()


if __name__ == "__main__": unittest.main()
