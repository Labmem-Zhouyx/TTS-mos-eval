# MOS Evaluation Toolkit

A small, self-contained tool for running MOS / ABX subjective tests over a
local-area network. Build for TTS systems but applicable to any audio
comparison study.

Key properties:

- **One-click start**: drop your audio in, run `python run.py`, share the URL.
- **Multi-panel, multi-dimension**: any combination of N-MOS / S-MOS / I-MOS
  and ABX preference is supported via per-panel YAML.
- **Drafts auto-saved** to JSON on every interaction; raters can leave and
  resume.
- **No database**: each rater is one JSON file under `data/results/`.
- **CSV + Markdown reports** with mean, 95% CI, ABX win rate and binomial
  p-value.

## 1. Install

Python 3.9+.

```bash
cd mos_eval
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Drop your audio in

The scanner walks `data/audio/<panel>/<sample>/`.  Each first-level
directory under `data/audio/` becomes one evaluation panel.  Built-in
templates are provided for the four panel names below, so you only need
to put the audio in.

```
data/audio/
├── zeroshot/                     # zero-shot voice cloning, N-MOS + S-MOS
│   ├── panel.yaml                # (optional) override panel config
│   └── sample_en_001/
│       ├── reference.wav         # required for this panel
│       ├── ground_truth.wav      # optional, shown as upper-bound reference
│       ├── VoxCPM2.wav
│       ├── VoxCPM1.5.wav
│       ├── LongCat-Audio-DiT.wav
│       ├── FishAudio_S2.wav
│       ├── Qwen3-TTS.wav
│       └── meta.json             # {"text": "...", "language": "en"}
├── multilingual/                 # multilingual, N-MOS only
│   └── sample_de_002/
│       ├── ground_truth.wav
│       ├── VoxCPM2.wav
│       ├── ElevenLabs.wav
│       ├── MiniMax-Speech.wav
│       ├── FishAudio_S2.wav
│       └── meta.json             # {"text": "...", "language": "de"}
├── controllable/                 # voice design + controllable cloning
│   └── sample_en_003/
│       ├── VoxCPM2.wav
│       ├── Qwen3-TTS-12Hz-1.7B-VD.wav
│       ├── Mimo-Audio-7B-Instruct.wav
│       ├── Hume.wav
│       └── meta.json             # {"text": "...", "instruction": "...", "subtask": "APS"}
└── abx/                          # ABX preference (optional)
    └── pair_001/
        ├── reference.wav         # the X
        ├── A.wav                 # output of system_a
        ├── B.wav                 # output of system_b
        └── meta.json             # {"system_a": "VoxCPM2", "system_b": "FishAudio_S2"}
```

Rules the scanner follows:

- Any file named `reference.wav` or `ground_truth.wav` is treated as the
  reference / GT audio for the sample.
- For MOS panels, every other `*.wav` is treated as one **system** to
  rate; the system name is the file stem (`VoxCPM2.wav` ⇒ `VoxCPM2`).
- For ABX panels, the audio files must be `reference.wav`, `A.wav`, `B.wav`,
  and `meta.json` must include `system_a` and `system_b` for aggregation.
- Each sample directory should contain a `meta.json` with at least the
  fields shown above; it is optional but recommended.
- System order in the UI is randomized per (panel, sample, rater), so the
  system identity never leaks into the listener.

Built-in panel templates (used automatically if `panel.yaml` is absent):

| panel directory name | type | dimensions     | reference | instruction |
| -------------------- | ---- | -------------- | --------- | ----------- |
| `zeroshot`           | mos  | N-MOS, S-MOS   | required  | no          |
| `multilingual`       | mos  | N-MOS          | optional  | no          |
| `controllable`       | mos  | N-MOS, I-MOS   | optional  | shown       |
| `abx`                | abx  | preference (A/B/tie) | required | no    |

You can override any of the above (titles, dimensions, hints, languages)
by placing a `panel.yaml` in the panel directory.  See the example files
under `data/audio/*/panel.yaml`.

## 3. Run the server

```bash
python run.py                 # default 0.0.0.0:8000
python run.py --port 9000
```

The console prints the URL.  Share it with your raters on the same LAN.
Each rater opens the URL, enters a nickname, and starts rating; their
progress is auto-saved both in `localStorage` (so they can come back
after closing the tab) and on the server (one JSON file per rater).

## 4. Aggregate the results

```bash
python scripts/aggregate.py
```

This walks `data/results/*.json`, computes per-system per-dimension
means with 95% confidence intervals (Student-t), ABX win rates and
two-sided binomial p-values against H0 = 0.5, and writes:

```
data/reports/summary.json          # everything in one JSON
data/reports/summary.md            # readable summary
data/reports/mos_summary.csv       # one row per (panel, system, dimension)
data/reports/abx_summary.csv       # one row per (panel, system_a, system_b)
```

By default only submitted panels are aggregated.  Pass
`--include-drafts` to include unfinished ones during a live session.

## 5. Project layout

```
mos_eval/
├── run.py                         # one-click entry
├── requirements.txt
├── server/
│   ├── main.py                    # FastAPI app
│   ├── scanner.py                 # parses data/audio/* into panels
│   ├── storage.py                 # atomic JSON read/write
│   ├── models.py                  # request/response schemas
│   └── analytics.py               # MOS + ABX statistics
├── static/
│   ├── index.html
│   ├── css/style.css
│   └── js/{app.js, i18n.js}
├── scripts/
│   └── aggregate.py               # CLI -> data/reports/
└── data/
    ├── audio/                     # you drop audio here
    ├── results/                   # auto-generated rater JSONs
    └── reports/                   # CSV / Markdown summaries
```

## 6. FAQ

**Q: Can a single rater split the work into multiple sessions?**
Yes. The UI uses `localStorage` to remember the session id and the current
view, so closing the tab and reopening the URL continues from the last
sample.  The server keeps the same JSON file and merges new ratings into
the existing panels by panel name.

**Q: How do I add a custom panel that is not zeroshot / multilingual / controllable / abx?**
Create the directory, then drop a `panel.yaml` inside.  Use one of the
`data/audio/*/panel.yaml` files in this repo as a starting point.

**Q: How is system order kept anonymous?**
The UI re-shuffles systems per (panel, sample) and persists the order in
`localStorage`, so within a rater the order is stable but independent
across raters.  The display label is `System 1`, `System 2`, ..., never
the actual model name or letter that might be confused with the ABX
panel choices.

**Q: Can a rater discover the system identity from the audio URL?**
No.  Audio files are not served through a static mount.  Every audio
path is registered behind an opaque token of the form ``/audio/<sha1>``,
where the underlying salt is regenerated on every server start.  The
``<audio>`` element exposes only the token, browser downloads are
disabled via ``controlslist="nodownload"``, the right-click context
menu is suppressed, and the HTTP filename returned by the server is the
token itself, not the original file name.  The on-disk file name and
the panel/sample directory structure are therefore never visible to the
listener.

**Q: How do I extend ABX into A/B preference with no reference?**
Simply omit `reference.wav` in the pair directory and set
`need_reference: false` in the panel YAML.  The UI hides the reference
strip automatically when the audio is missing.

**Q: Where are the binomial / t-tests defined?**
See `server/analytics.py`.  When SciPy is available we use exact
`scipy.stats.binomtest` and `scipy.stats.t.ppf`; otherwise we fall back
to a normal approximation.
