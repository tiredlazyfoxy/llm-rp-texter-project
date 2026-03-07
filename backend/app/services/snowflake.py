import threading
import time

# Epoch: 2025-01-01T00:00:00Z in milliseconds
_EPOCH_MS = 1_735_689_600_000

_SEQUENCE_BITS = 19
_MACHINE_BITS = 3

_MAX_SEQUENCE = (1 << _SEQUENCE_BITS) - 1  # 524287
_MACHINE_ID = 0  # Fixed for single-instance deployment


class _SnowflakeGenerator:
    def __init__(self, machine_id: int = _MACHINE_ID) -> None:
        self._machine_id = machine_id & ((1 << _MACHINE_BITS) - 1)
        self._sequence = 0
        self._last_ms = -1
        self._lock = threading.Lock()

    def generate_id(self) -> int:
        with self._lock:
            now_ms = int(time.time() * 1000) - _EPOCH_MS

            if now_ms == self._last_ms:
                self._sequence += 1
                if self._sequence > _MAX_SEQUENCE:
                    # Wait for next millisecond
                    while now_ms == self._last_ms:
                        now_ms = int(time.time() * 1000) - _EPOCH_MS
                    self._sequence = 0
            else:
                self._sequence = 0

            self._last_ms = now_ms

            return (
                (now_ms << (_SEQUENCE_BITS + _MACHINE_BITS))
                | (self._sequence << _MACHINE_BITS)
                | self._machine_id
            )


_generator = _SnowflakeGenerator()


def generate_id() -> int:
    return _generator.generate_id()
