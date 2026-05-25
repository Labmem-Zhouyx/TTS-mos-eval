"""Quick smoke test for scanner + analytics. Run::

    python scripts/_self_check.py

It populates a temporary directory with mock audio paths and rater JSON
files, then walks them through the scanner and aggregator to make sure
the full plumbing works end-to-end.  Real audio files are not required;
the scanner only checks for files by extension.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.scanner import scan_panels, panel_to_dict  # noqa: E402
from server.analytics import aggregate, load_sessions, write_all  # noqa: E402


def write_dummy_audio(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # 44 byte WAV header so any audio tool happily opens it
    path.write_bytes(
        b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"\x44\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        audio = root / "audio"

        # zeroshot panel
        s1 = audio / "zeroshot" / "sample_001"
        write_dummy_audio(s1 / "reference.wav")
        for sys_name in ("VoxCPM2", "FishAudio_S2", "Qwen3-TTS"):
            write_dummy_audio(s1 / f"{sys_name}.wav")
        (s1 / "meta.json").write_text(json.dumps({"text": "hello"}), encoding="utf-8")

        # ABX panel
        ab = audio / "abx" / "pair_001"
        write_dummy_audio(ab / "reference.wav")
        write_dummy_audio(ab / "A.wav")
        write_dummy_audio(ab / "B.wav")
        (ab / "meta.json").write_text(
            json.dumps({"system_a": "VoxCPM2", "system_b": "FishAudio_S2"}),
            encoding="utf-8",
        )

        # set scanner data root
        os.environ["MOS_EVAL_DATA_ROOT"] = str(root)
        panels = scan_panels(audio)
        assert any(p.name == "zeroshot" for p in panels), "zeroshot panel missing"
        assert any(p.name == "abx" for p in panels), "abx panel missing"
        for p in panels:
            d = panel_to_dict(p)
            print(f"panel {p.name}: {len(d['samples'])} sample(s), type={p.type}")

        # Create two mock rater sessions
        results = root / "results"
        results.mkdir(parents=True, exist_ok=True)
        sessions = [
            {
                "session_id": "rater_a",
                "nickname": "alice",
                "language": "zh",
                "submitted_at": "2026-04-21T10:00:00",
                "panels": [
                    {
                        "panel": "zeroshot",
                        "status": "submitted",
                        "samples": [
                            {
                                "sample_id": "sample_001",
                                "ratings": [
                                    {"system": "VoxCPM2", "scores": {"n_mos": 4.5, "s_mos": 4}},
                                    {"system": "FishAudio_S2", "scores": {"n_mos": 4, "s_mos": 4}},
                                    {"system": "Qwen3-TTS", "scores": {"n_mos": 4, "s_mos": 3.5}},
                                ],
                            }
                        ],
                    },
                    {
                        "panel": "abx",
                        "status": "submitted",
                        "samples": [
                            {
                                "sample_id": "pair_001",
                                "ratings": [],
                                "abx_choice": "A",
                                "meta": {"system_a": "VoxCPM2", "system_b": "FishAudio_S2"},
                            }
                        ],
                    },
                ],
            },
            {
                "session_id": "rater_b",
                "nickname": "bob",
                "language": "en",
                "submitted_at": "2026-04-21T11:00:00",
                "panels": [
                    {
                        "panel": "zeroshot",
                        "status": "submitted",
                        "samples": [
                            {
                                "sample_id": "sample_001",
                                "ratings": [
                                    {"system": "VoxCPM2", "scores": {"n_mos": 4, "s_mos": 4.5}},
                                    {"system": "FishAudio_S2", "scores": {"n_mos": 4.5, "s_mos": 4}},
                                    {"system": "Qwen3-TTS", "scores": {"n_mos": 3.5, "s_mos": 3.5}},
                                ],
                            }
                        ],
                    },
                    {
                        "panel": "abx",
                        "status": "submitted",
                        "samples": [
                            {
                                "sample_id": "pair_001",
                                "ratings": [],
                                "abx_choice": "tie",
                                "meta": {"system_a": "VoxCPM2", "system_b": "FishAudio_S2"},
                            }
                        ],
                    },
                ],
            },
        ]
        for s in sessions:
            (results / f"{s['session_id']}.json").write_text(
                json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        report = aggregate(load_sessions(results))
        reports_dir = root / "reports"
        paths = write_all(report, reports_dir)
        print("sessions:", report.sessions, "raters:", report.raters)
        for s in report.mos:
            print(
                f"  MOS {s.panel}/{s.system}/{s.dimension}: "
                f"n={s.n} mean={s.mean:.2f} ci=[{s.ci_low:.2f},{s.ci_high:.2f}]"
            )
        for s in report.abx:
            print(
                f"  ABX {s.panel} {s.system_a} vs {s.system_b}: "
                f"A={s.a_wins} B={s.b_wins} tie={s.ties} p={s.p_value:.3f}"
            )
        for k, v in paths.items():
            print("  wrote", k, "->", v)


if __name__ == "__main__":
    main()
