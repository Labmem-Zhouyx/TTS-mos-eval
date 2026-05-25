"""Verify that no audio URL emitted by /api/panels leaks the on-disk path.

Spins up a temporary data root with mock audio files, calls scan_panels,
serialises panels through panel_to_dict, then asserts that every audio
URL is of the form /audio/<token> and never contains the system name or
sample directory.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.scanner import (  # noqa: E402
    panel_to_dict,
    resolve_token,
    scan_panels,
)


def write_dummy_audio(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"\x44\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        audio = root / "audio"

        zs = audio / "zeroshot" / "sample_001"
        write_dummy_audio(zs / "reference.wav")
        write_dummy_audio(zs / "ground_truth.wav")
        for name in ("VoxCPM2", "FishAudio_S2", "Qwen3-TTS", "LongCat-Audio-DiT"):
            write_dummy_audio(zs / f"{name}.wav")

        ab = audio / "abx" / "pair_001"
        write_dummy_audio(ab / "reference.wav")
        write_dummy_audio(ab / "A.wav")
        write_dummy_audio(ab / "B.wav")

        os.environ["MOS_EVAL_DATA_ROOT"] = str(root)
        panels = scan_panels(audio)

        leak_terms = (
            "VoxCPM2",
            "FishAudio",
            "Qwen3",
            "LongCat",
            "sample_001",
            "pair_001",
            ".wav",
            "/zeroshot/",
            "/abx/",
        )

        ok = True
        token_pattern = re.compile(r"^/audio/[0-9a-f]{16,}$")
        seen = 0
        for panel in panels:
            d = panel_to_dict(panel)
            for sample in d["samples"]:
                urls = [a["url"] for a in sample["audio"]]
                if sample.get("reference_url"):
                    urls.append(sample["reference_url"])
                if sample.get("ground_truth_url"):
                    urls.append(sample["ground_truth_url"])
                for url in urls:
                    seen += 1
                    if not token_pattern.match(url):
                        print(f"FAIL bad shape: {url}")
                        ok = False
                        continue
                    for term in leak_terms:
                        if term in url:
                            print(f"FAIL leak '{term}' in {url}")
                            ok = False
                    token = url.rsplit("/", 1)[-1]
                    path = resolve_token(token)
                    if path is None or not path.is_file():
                        print(f"FAIL unresolvable token: {token}")
                        ok = False

        print(f"checked {seen} URLs across {len(panels)} panels")
        if not ok:
            sys.exit(1)
        print("OK: every audio URL is an opaque token; no path leakage detected")


if __name__ == "__main__":
    main()
