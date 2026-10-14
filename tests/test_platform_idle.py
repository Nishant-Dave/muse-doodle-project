"""Windows idle-detection tests: tick functions must come from kernel32.

Regression coverage for the 2026-10-13/14 bug where
system_idle_seconds() resolved GetTickCount64/GetTickCount from user32
(where they do not exist), so idle seconds were always None on Windows.
"""

import ctypes
import logging

import pytest

from doodle_mvp.platform.adapter import WindowsPlatformAdapter


class _Tick:
    """Callable stand-in for a Win32 tick function."""

    def __init__(self, value=None):
        self.value = value
        self.calls = 0
        self.restype = None  # the adapter assigns this

    def __call__(self):
        self.calls += 1
        if self.value is None:
            raise AttributeError("no such tick function")
        return self.value


class FakeUser32:
    """Exposes ONLY GetLastInputInfo -- like the real user32, it has no
    GetTickCount functions. If the adapter touches user32 for ticks, the
    AttributeError path proves the regression is back."""

    def __init__(self, dw_time):
        self._dw_time = dw_time

    def GetLastInputInfo(self, ptr):
        # LASTINPUTINFO layout: cbSize, dwTime (two c_uints)
        arr = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_uint * 2)).contents
        arr[1] = self._dw_time
        return 1


class FakeKernel32:
    def __init__(self, tick64=None, tick32=None):
        self.GetTickCount64 = _Tick(tick64)
        self.GetTickCount = _Tick(tick32)


class FakeWindll:
    def __init__(self, user32, kernel32):
        self.user32 = user32
        self.kernel32 = kernel32


@pytest.fixture()
def adapter(monkeypatch):
    def make(dw_time, tick64, tick32=None):
        fake = FakeWindll(FakeUser32(dw_time), FakeKernel32(tick64, tick32))
        monkeypatch.setattr(ctypes, "windll", fake, raising=False)
        return WindowsPlatformAdapter()

    return make


def test_idle_seconds_uses_kernel32_tick64(adapter):
    eng = adapter(dw_time=1000, tick64=6000)
    assert eng.system_idle_seconds() == pytest.approx(5.0)


def test_tick64_is_preferred_over_tick32(adapter):
    eng = adapter(dw_time=0, tick64=2000, tick32=999999)
    assert eng.system_idle_seconds() == pytest.approx(2.0)
    assert eng._kernel32.GetTickCount.calls == 0


def test_tick32_fallback_masks_49_day_wrap(adapter):
    # now wrapped just past zero; raw subtraction would be hugely negative
    eng = adapter(dw_time=0xFFFFFF00, tick64=None, tick32=100)
    assert eng.system_idle_seconds() == pytest.approx(0.356)


def test_failure_warning_logged_once(adapter, caplog):
    class FailingUser32:
        def GetLastInputInfo(self, ptr):
            raise RuntimeError("boom")

    import ctypes as _ct

    eng = adapter(dw_time=0, tick64=0)
    eng._user32 = FailingUser32()
    with caplog.at_level(logging.WARNING, logger="doodle_mvp.platform.adapter"):
        assert eng.system_idle_seconds() is None
        assert eng.system_idle_seconds() is None
    warnings = [r for r in caplog.records if "GetLastInputInfo failed" in r.message]
    assert len(warnings) == 1


def test_none_when_handles_unavailable():
    eng = WindowsPlatformAdapter.__new__(WindowsPlatformAdapter)
    eng._user32 = None
    eng._kernel32 = None
    eng._idle_warned = False
    assert eng.system_idle_seconds() is None
