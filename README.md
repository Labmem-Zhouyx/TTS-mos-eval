# MOS Evaluation Toolkit

A lightweight, self-contained toolkit for running MOS and ABX subjective
listening tests over a local network. It is designed for TTS evaluation,
but can also be used for any audio comparison study that needs:

- anonymous system presentation
- startup-seeded sample/system randomization
- MOS scoring with multiple dimensions
- ABX / A-B preference tests
- automatic draft saving
- offline JSON/CSV/Markdown reporting

The project deliberately avoids databases and heavy dependencies. You drop
audio into the expected folder structure, start the server, and share the
URL with raters on the same LAN.

## Highlights

- **One-command local deployment**: run `python run.py`
- **Panel-based evaluation**: `zeroshot`, `multilingual`, `controllable`, `cmos`, `abx`
- **Flexible dimensions**: any combination of `N-MOS`, `S-MOS`, `I-MOS`, or custom choices via `panel.yaml`
- **Anonymous listening**: audio is served through opaque tokens instead of file paths
- **Auto-save by interaction**: browser + server both persist draft progress
- **Clean reporting**: aggregate to JSON, Markdown, and CSV with `mean ± 95% CI`

## Quick Start

### 1. Install

Python 3.9+.

```bash
cd mos_eval
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Prepare audio

The scanner walks:

```text
data/audio/<panel>/<sample>/
```

Each first-level directory under `data/audio/` becomes one evaluation panel.
Built-in templates are provided for the five panel names below, so in the
common case you only need to drop audio into place.

```text
data/audio/
├── zeroshot/                     # zero-shot cloning, N-MOS + S-MOS
│   ├── panel.yaml                # optional override
│   └── sample_en_001/
│       ├── reference.wav
│       ├── ground_truth.wav      # optional
│       ├── VoxCPM2.wav
│       ├── VoxCPM1.5.wav
│       ├── LongCat-Audio-DiT.wav
│       ├── FishAudio_S2.wav
│       ├── Qwen3-TTS.wav
│       └── meta.json
├── multilingual/                 # multilingual synthesis, N-MOS + S-MOS
│   └── sample_de_002/
│       ├── ground_truth.wav      # optional
│       ├── VoxCPM2.wav
│       ├── ElevenLabs.wav
│       ├── MiniMax-Speech.wav
│       ├── FishAudio_S2.wav
│       └── meta.json
├── controllable/                 # voice design / controllable cloning
│   └── sample_en_003/
│       ├── VoxCPM2.wav
│       ├── Qwen3-TTS-12Hz-1.7B-VD.wav
│       ├── Mimo-Audio-7B-Instruct.wav
│       ├── Hume.wav
│       └── meta.json
├── cmos/                         # comparative MOS against anchor system
│   └── sample_en_004/
│       ├── VoxCPM2.wav           # anchor / proposed system
│       ├── FishAudio_S2.wav
│       ├── Qwen3-TTS.wav
│       └── meta.json
└── abx/                          # ABX or A/B preference
    └── pair_001/
        ├── reference.wav         # optional if configured
        ├── A.wav
        ├── B.wav
        └── meta.json
```

### 3. Start the server

```bash
python run.py
python run.py --port 9000
```

The server prints the local URL. Share that URL with raters on the same LAN.

### 4. Aggregate results

```bash
python scripts/aggregate.py
```

This writes:

```text
data/reports/summary.json
data/reports/summary.md
data/reports/mos_summary.csv
data/reports/abx_summary.csv
```

By default only submitted panels are aggregated. Use `--include-drafts` to
include unfinished panels during live collection.

## Built-in Panel Templates

| panel directory name | type | dimensions | reference | instruction |
| --- | --- | --- | --- | --- |
| `zeroshot` | mos | `N-MOS`, `S-MOS` | required | no |
| `multilingual` | mos | `N-MOS`, `S-MOS` | optional | no |
| `controllable` | mos | `N-MOS`, `I-MOS` | optional | shown |
| `cmos` | cmos | comparative score from `-3` to `3` | optional | optional |
| `abx` | abx | preference (`A` / `B` / `tie`) | required by default | no |

You can override titles, dimensions, hints, or panel behavior by placing a
`panel.yaml` in the panel directory. See the example files under
`data/audio/*/panel.yaml`.

## Scanner Rules

- `reference.wav` and `ground_truth.wav` have reserved meanings.
- In MOS panels, every other `*.wav` is treated as one system to rate.
- In `cmos` panels, one system is treated as the anchor / proposed system (default: `VoxCPM2`), and all other systems are scored relative to it on a `-3 ... 3` scale. The CMOS score is the result of comparison with the proposed model.
- In ABX panels, audio must be named `reference.wav`, `A.wav`, and `B.wav`.
- `meta.json` is optional but strongly recommended.
- Sample order and system order are shuffled once per server startup using a process-local random seed.

## Report Format

`mos_summary.csv` contains one row per `(panel, system, dimension)` with:

- `mean`
- `std`
- `ci_margin`
- `mean_pm_95ci`
- `ci_low`
- `ci_high`

The Markdown summary uses the compact format:

```text
mean ± 95% CI
```

For example:

```text
4.32 ± 0.18
```

## Repository Layout

```text
mos_eval/
├── run.py
├── requirements.txt
├── README.md
├── CONTRIBUTING.md
├── LICENSE
├── server/
│   ├── main.py
│   ├── scanner.py
│   ├── storage.py
│   ├── models.py
│   └── analytics.py
├── static/
│   ├── index.html
│   ├── css/style.css
│   └── js/{app.js,i18n.js}
├── scripts/
│   ├── aggregate.py
│   ├── _self_check.py
│   └── _anon_check.py
└── data/
    ├── audio/      # user-provided audio
    ├── results/    # auto-generated session JSONs
    └── reports/    # auto-generated aggregate reports
```

## Anonymity Design

The frontend never sees the original audio path or file name.

- Audio files are not mounted as static files.
- Each on-disk file is registered as an opaque `/audio/<token>` URL.
- Browser downloads are disabled in the audio element.
- The returned filename is the token itself, not the original system name.
- The UI labels systems as `System 1`, `System 2`, ... rather than real names.

This helps reduce rating leakage in subjective studies.

## FAQ

**Can a single rater split the work into multiple sessions?**  
Yes. The browser stores session state in `localStorage`, and the server also
keeps one JSON file per rater.

**How do I add a custom panel?**  
Create a new panel directory under `data/audio/` and add a `panel.yaml`.

**Can ABX work without a reference file?**  
Yes. Omit `reference.wav` and set `need_reference: false` in `panel.yaml`.

**Where are the statistical tests implemented?**  
See `server/analytics.py`. When SciPy is available, the toolkit uses
Student-t confidence intervals and exact binomial tests.
