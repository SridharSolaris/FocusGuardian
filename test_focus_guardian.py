"""
FocusGuardian v2.2 — Test Suite
================================
Run with: pytest test_focus_guardian.py -v

Tests pure-logic components (no Tkinter, no psutil, no network).
GUI components are tested via mocked widgets where needed.
"""

import json
import os
import sys
import tempfile
import types
from datetime import datetime, timedelta, time as dtime, date

import pytest

# ---------------------------------------------------------------------------
# Mock tkinter and psutil BEFORE importing the module
# ---------------------------------------------------------------------------

def _make_mock_widget():
    """Create a generic mock widget class for Tkinter/ttk."""
    class MockWidget:
        def __init__(self, *args, **kwargs):
            pass
        def config(self, **kwargs):
            pass
        def configure(self, *args, **kwargs):
            pass
        def grid(self, *args, **kwargs):
            pass
        def pack(self, *args, **kwargs):
            pass
        def set(self, value):
            pass
        def get(self):
            return 0
        def delete(self, *args):
            pass
        def insert(self, *args):
            pass
        def bind(self, *args, **kwargs):
            pass
        def trace_add(self, *args, **kwargs):
            pass
        def tk_popup(self, *args, **kwargs):
            pass
        def selection_clear(self, *args):
            pass
        def selection_set(self, *args):
            pass
        def nearest(self, y):
            return 0
        def curselection(self):
            return ()
        def destroy(self):
            pass
        def focus_set(self):
            pass
        def current(self, *args):
            return 0 if not args else None
        def wait_window(self, w):
            pass
        def theme_use(self, *args):
            pass
        def index(self, idx):
            return 0
        def select(self):
            return ""
        def heading(self, *args, **kwargs):
            pass
        def column(self, *args, **kwargs):
            pass
        def get_children(self):
            return []
        def yview(self, *args):
            pass
        values = []
        def __setitem__(self, key, value):
            pass
        def __getitem__(self, key):
            if key == "state":
                return "normal"
            return 0
    return MockWidget


# Install mocks
_mock_tk = types.ModuleType("tkinter")
_mock_tk.Tk = _make_mock_widget()
_mock_tk.TclError = Exception
_mock_tk.END = "end"

for _name in ["Frame", "Label", "Button", "Entry", "Listbox", "Text",
              "Canvas", "BooleanVar", "IntVar", "StringVar", "Menu", "Toplevel"]:
    setattr(_mock_tk, _name, _make_mock_widget())

_mock_menu = _make_mock_widget()
_mock_menu.tearoff = 0
_mock_tk.Menu = _mock_menu

_mock_tk.messagebox = types.ModuleType("tkinter.messagebox")
for _name in ["showinfo", "showwarning", "askyesno", "showerror"]:
    setattr(_mock_tk.messagebox, _name, lambda *a, **k: True)

_mock_tk.ttk = types.ModuleType("tkinter.ttk")
for _name in ["Style", "Notebook", "Frame", "Label", "Button", "Entry",
              "Progressbar", "Checkbutton", "Scrollbar", "Combobox", "Treeview"]:
    setattr(_mock_tk.ttk, _name, _make_mock_widget())

sys.modules["tkinter"] = _mock_tk
sys.modules["tkinter.messagebox"] = _mock_tk.messagebox
sys.modules["tkinter.ttk"] = _mock_tk.ttk

_mock_psutil = types.ModuleType("psutil")
_mock_psutil.process_iter = lambda attrs=None: []
_mock_psutil.NoSuchProcess = Exception
_mock_psutil.AccessDenied = Exception
_mock_font = types.ModuleType("tkinter.font")
class _MockFont:
    def __init__(self, *a, **k): pass
    def measure(self, text): return len(text) * 7
    def metrics(self, opt): return 16
_mock_font.Font = _MockFont
sys.modules["tkinter.font"] = _mock_font

sys.modules["psutil"] = _mock_psutil

# Now import the module under test
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "focus_guardian",
    os.path.join(os.path.dirname(__file__), "focus_guardian.py")
)
fg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fg)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_config_dir(tmp_path, monkeypatch):
    """Redirect all config paths to a temp directory."""
    monkeypatch.setattr(fg, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(fg, "CONFIG_FILE", str(tmp_path / "config.json"))
    monkeypatch.setattr(fg, "DB_FILE", str(tmp_path / "sessions.db"))
    monkeypatch.setattr(fg, "LOG_FILE", str(tmp_path / "focus_guardian.log"))
    monkeypatch.setattr(fg, "HTML_FILE", str(tmp_path / "stay_focused.html"))
    return tmp_path


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestConfig:
    def test_default_config_has_profiles(self):
        assert "profiles" in fg.DEFAULT_CONFIG
        assert len(fg.DEFAULT_CONFIG["profiles"]) == 3
        assert "schedules" in fg.DEFAULT_CONFIG
        assert "active_profile" in fg.DEFAULT_CONFIG

    def test_default_profiles_have_blocklists(self):
        for prof in fg.DEFAULT_CONFIG["profiles"]:
            assert "name" in prof
            assert "blocklist" in prof
            assert "app_blocklist" in prof
            assert isinstance(prof["blocklist"], list)
            assert isinstance(prof["app_blocklist"], list)

    def test_load_config_creates_dir(self, tmp_config_dir):
        cfg = fg.load_config()
        assert os.path.exists(str(tmp_config_dir))

    def test_load_fresh_config(self, tmp_config_dir):
        cfg = fg.load_config()
        assert len(cfg["profiles"]) == 3
        assert cfg["profiles"][0]["name"] == "Social Media"
        assert cfg["active_profile"] == 0

    def test_save_and_load_roundtrip(self, tmp_config_dir):
        cfg = fg.load_config()
        cfg["profiles"].append({
            "name": "Test",
            "blocklist": ["test.com"],
            "app_blocklist": ["test.exe"],
        })
        cfg["active_profile"] = 3
        cfg["schedules"] = [{
            "name": "Work Hours",
            "profile": "Deep Work",
            "start_time": "09:00",
            "end_time": "17:00",
            "days": [0, 1, 2, 3, 4],
            "enabled": True,
        }]
        fg.save_config(cfg)
        cfg2 = fg.load_config()
        assert len(cfg2["profiles"]) == 4
        assert cfg2["profiles"][3]["name"] == "Test"
        assert cfg2["active_profile"] == 3
        assert len(cfg2["schedules"]) == 1
        assert cfg2["schedules"][0]["name"] == "Work Hours"

    def test_migration_old_flat_config(self, tmp_config_dir):
        """Old v2.1 config with flat blocklist/app_blocklist migrates to profiles."""
        old_cfg = {
            "work_duration_min": 30,
            "blocklist": ["youtube.com", "facebook.com"],
            "app_blocklist": ["discord.exe"],
            "strict_mode": False,
        }
        with open(fg.CONFIG_FILE, "w") as f:
            json.dump(old_cfg, f)

        cfg = fg.load_config()
        assert "profiles" in cfg
        # v2.7+: migration uses 3 default profiles instead of single "Default"
        assert len(cfg["profiles"]) == 3
        assert cfg["profiles"][0]["name"] == "Social Media"
        assert "youtube.com" in cfg["profiles"][0]["blocklist"]
        assert "discord.exe" in cfg["profiles"][0]["app_blocklist"]
        assert cfg["active_profile"] == 0

    def test_active_profile_clamped(self, tmp_config_dir):
        cfg = fg.load_config()
        cfg["active_profile"] = 999
        fg.save_config(cfg)
        cfg2 = fg.load_config()
        assert cfg2["active_profile"] == 0

    def test_corrupt_config_falls_back(self, tmp_config_dir):
        with open(fg.CONFIG_FILE, "w") as f:
            f.write("NOT JSON {{{")
        cfg = fg.load_config()
        assert "profiles" in cfg
        assert len(cfg["profiles"]) == 3


# ---------------------------------------------------------------------------
# HostsManager tests
# ---------------------------------------------------------------------------

class TestHostsManager:
    def test_strip_blocks_removes_section(self):
        content = (
            "127.0.0.1 localhost\n"
            f"{fg.BEGIN_MARKER}\n"
            "127.0.0.1  youtube.com\n"
            "127.0.0.1  facebook.com\n"
            f"{fg.END_MARKER}\n"
            "10.0.0.1 other\n"
        )
        result = fg.HostsManager._strip_blocks(content)
        assert "youtube.com" not in result
        assert "facebook.com" not in result
        assert fg.BEGIN_MARKER not in result
        assert fg.END_MARKER not in result
        assert "localhost" in result
        assert "10.0.0.1 other" in result

    def test_strip_blocks_no_markers(self):
        content = "127.0.0.1 localhost\n"
        result = fg.HostsManager._strip_blocks(content)
        assert result == "127.0.0.1 localhost\n"

    def test_has_orphaned_blocks_false_when_no_file(self, tmp_config_dir):
        hm = fg.HostsManager()
        assert hm.has_orphaned_blocks() is False

    def test_has_orphaned_blocks_true(self, tmp_config_dir, monkeypatch):
        hosts_file = str(tmp_config_dir / "hosts")
        with open(hosts_file, "w") as f:
            f.write(f"127.0.0.1 localhost\n{fg.BEGIN_MARKER}\n127.0.0.1 youtube.com\n{fg.END_MARKER}\n")
        monkeypatch.setattr(fg, "HOSTS_PATH", hosts_file)
        hm = fg.HostsManager()
        assert hm.has_orphaned_blocks() is True

    def test_apply_blocks_adds_section(self, tmp_config_dir, monkeypatch):
        hosts_file = str(tmp_config_dir / "hosts")
        with open(hosts_file, "w") as f:
            f.write("127.0.0.1 localhost\n")
        monkeypatch.setattr(fg, "HOSTS_PATH", hosts_file)
        hm = fg.HostsManager()
        ok, msg = hm.apply_blocks(["youtube.com", "facebook.com"])
        assert ok is True
        with open(hosts_file) as f:
            content = f.read()
        assert "youtube.com" in content
        assert "facebook.com" in content
        assert fg.BEGIN_MARKER in content
        assert fg.END_MARKER in content

    def test_remove_blocks_cleans_section(self, tmp_config_dir, monkeypatch):
        hosts_file = str(tmp_config_dir / "hosts")
        with open(hosts_file, "w") as f:
            f.write(f"127.0.0.1 localhost\n{fg.BEGIN_MARKER}\n127.0.0.1 youtube.com\n{fg.END_MARKER}\n")
        monkeypatch.setattr(fg, "HOSTS_PATH", hosts_file)
        hm = fg.HostsManager()
        ok, msg = hm.remove_blocks()
        assert ok is True
        with open(hosts_file) as f:
            content = f.read()
        assert "youtube.com" not in content
        assert "localhost" in content


# ---------------------------------------------------------------------------
# AppBlocker tests
# ---------------------------------------------------------------------------

class TestAppBlocker:
    @pytest.mark.parametrize("proc_name,blocked,expected", [
        ("discord.exe", "discord.exe", True),
        ("Discord.EXE", "discord.exe", True),
        ("discord.exe", "discord", True),
        ("discord", "discord.exe", True),
        ("notepad.exe", "discord.exe", False),
        ("steam.exe", "discord.exe", False),
        ("STEAM.EXE", "steam.exe", True),
    ])
    def test_matches(self, proc_name, blocked, expected):
        assert fg.AppBlocker._matches(proc_name, blocked) is expected

    def test_start_and_stop(self):
        blocker = fg.AppBlocker(["nonexistent.exe"], check_interval=1)
        blocker.start()
        import time
        time.sleep(0.5)
        assert blocker._running is True
        blocker.stop()
        assert blocker._running is False

    def test_empty_blocklist(self):
        blocker = fg.AppBlocker([], check_interval=1)
        assert blocker.app_blocklist == []

    def test_killed_count_starts_zero(self):
        blocker = fg.AppBlocker(["test.exe"])
        assert blocker._killed_count == 0
        assert blocker._killed_names == []


# ---------------------------------------------------------------------------
# SessionTracker tests
# ---------------------------------------------------------------------------

class TestSessionTracker:
    def test_log_and_retrieve(self, tmp_config_dir):
        tracker = fg.SessionTracker()
        start = datetime.now() - timedelta(minutes=25)
        end = datetime.now()
        tracker.log_session(start, end, 1500, "work", completed=1)
        assert tracker.get_today_work_count() == 1
        stats = tracker.get_today_stats()
        assert "work" in stats
        assert stats["work"]["count"] == 1
        assert stats["work"]["seconds"] == 1500
        tracker.close()

    def test_total_stats(self, tmp_config_dir):
        tracker = fg.SessionTracker()
        tracker.log_session(datetime.now() - timedelta(minutes=25), datetime.now(),
                           1500, "work", completed=1)
        tracker.log_session(datetime.now() - timedelta(minutes=5), datetime.now(),
                           300, "short_break", completed=1)
        total = tracker.get_total_stats()
        assert total["total_sessions"] == 1  # only work sessions counted
        assert total["total_seconds"] == 1500
        tracker.close()

    def test_incomplete_session_not_counted_in_work_count(self, tmp_config_dir):
        tracker = fg.SessionTracker()
        tracker.log_session(datetime.now() - timedelta(minutes=10), datetime.now(),
                           600, "work", completed=0)
        assert tracker.get_today_work_count() == 0  # incomplete not counted
        tracker.close()

    def test_last_n_days(self, tmp_config_dir):
        tracker = fg.SessionTracker()
        tracker.log_session(datetime.now() - timedelta(days=3, minutes=25),
                           datetime.now() - timedelta(days=3),
                           1500, "work", completed=1)
        last7 = tracker.get_last_n_days(7)
        assert len(last7) >= 1
        tracker.close()


# ---------------------------------------------------------------------------
# MotivationalServer tests
# ---------------------------------------------------------------------------

class TestMotivationalServer:
    def test_start_stop(self):
        srv = fg.MotivationalServer(8901)
        assert srv.start() is True
        assert srv._running is True
        srv.stop()
        assert srv._running is False

    def test_serves_html(self):
        import urllib.request
        srv = fg.MotivationalServer(8902)
        srv.start()
        try:
            resp = urllib.request.urlopen("http://127.0.0.1:8902/", timeout=3)
            body = resp.read().decode()
            assert "Stay Focused" in body
            assert "FocusGuardian" in body
        finally:
            srv.stop()

    def test_double_start_safe(self):
        srv = fg.MotivationalServer(8903)
        assert srv.start() is True
        assert srv.start() is True  # idempotent
        srv.stop()


# ---------------------------------------------------------------------------
# ScheduleEngine tests
# ---------------------------------------------------------------------------

class TestScheduleEngine:
    def test_parse_time_valid(self):
        assert fg.ScheduleEngine._parse_time("09:30") == dtime(9, 30)
        assert fg.ScheduleEngine._parse_time("00:00") == dtime(0, 0)
        assert fg.ScheduleEngine._parse_time("23:59") == dtime(23, 59)

    def test_parse_time_invalid(self):
        assert fg.ScheduleEngine._parse_time("invalid") == dtime(9, 0)
        assert fg.ScheduleEngine._parse_time("") == dtime(9, 0)
        assert fg.ScheduleEngine._parse_time("25:99") == dtime(9, 0)

    @pytest.mark.parametrize("days,expected", [
        ([0, 1, 2, 3, 4], "Weekdays"),
        ([5, 6], "Weekends"),
        ([0, 1, 2, 3, 4, 5, 6], "Every day"),
        ([], "Never"),
        ([0, 2, 4], "Mon, Wed, Fri"),
        ([6], "Sun"),
    ])
    def test_format_days(self, days, expected):
        assert fg.ScheduleEngine.format_days(days) == expected


# ---------------------------------------------------------------------------
# Site normalisation tests
# ---------------------------------------------------------------------------

class TestSiteNormalisation:
    @pytest.mark.parametrize("input_site,expected", [
        ("https://www.youtube.com/watch", "www.youtube.com"),
        ("http://reddit.com", "reddit.com"),
        ("youtube.com", "youtube.com"),
        ("HTTPS://WWW.FACEBOOK.COM/", "www.facebook.com"),
        ("  Twitter.com  ", "twitter.com"),
        ("not_a_domain", ""),
        ("", ""),
        ("http://", ""),
    ])
    def test_normalise_site(self, input_site, expected):
        assert fg.FocusGuardianApp._normalise_site(input_site) == expected


# ---------------------------------------------------------------------------
# Duration formatting tests
# ---------------------------------------------------------------------------

class TestDurationFormatting:
    @pytest.mark.parametrize("seconds,expected", [
        (0, "0m"),
        (30, "0m"),
        (60, "1m"),
        (300, "5m"),
        (1500, "25m"),
        (3600, "1h 0m"),
        (5400, "1h 30m"),
        (90000, "25h 0m"),
    ])
    def test_fmt_dur(self, seconds, expected):
        assert fg.FocusGuardianApp._fmt_dur(seconds) == expected


# ---------------------------------------------------------------------------
# Logging tests
# ---------------------------------------------------------------------------

class TestLogging:
    def test_setup_logging_creates_file(self, tmp_config_dir):
        fg.setup_logging()
        assert os.path.exists(fg.LOG_FILE)

    def test_log_writes_message(self, tmp_config_dir):
        fg.setup_logging()
        fg.logger.info("TEST MESSAGE XYZ")
        with open(fg.LOG_FILE, "r") as f:
            content = f.read()
        assert "TEST MESSAGE XYZ" in content

    def test_log_includes_timestamp(self, tmp_config_dir):
        fg.setup_logging()
        fg.logger.info("timestamp test")
        with open(fg.LOG_FILE, "r") as f:
            content = f.read()
        # Log format includes date: YYYY-MM-DD HH:MM:SS
        assert datetime.now().strftime("%Y-%m-%d") in content


# ---------------------------------------------------------------------------
# Motivational HTML tests
# ---------------------------------------------------------------------------

class TestMotivationalHTML:
    def test_html_contains_site_name(self):
        html = fg.get_motivational_html("youtube.com")
        assert "youtube.com" in html

    def test_html_default_site(self):
        html = fg.get_motivational_html("")
        assert "this site" in html

    def test_html_has_stay_focused(self):
        html = fg.get_motivational_html("test.com")
        assert "Stay Focused" in html

    def test_html_writes_file(self, tmp_config_dir):
        fg.get_motivational_html("test.com")
        assert os.path.exists(fg.HTML_FILE)
        with open(fg.HTML_FILE, "r") as f:
            content = f.read()
        assert "__SITE__" not in content  # placeholder replaced


# ---------------------------------------------------------------------------
# Play bell tests
# ---------------------------------------------------------------------------

class TestPlayBell:
    def test_does_not_crash(self):
        fg.play_bell()  # should not raise


# ---------------------------------------------------------------------------
# is_admin tests
# ---------------------------------------------------------------------------

class TestIsAdmin:
    def test_returns_bool(self):
        result = fg.is_admin()
        assert isinstance(result, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
