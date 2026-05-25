"""Scan the data directory and build panel/sample definitions.

Directory convention
--------------------
::

    data/audio/<panel_name>/<sample_id>/
        reference.wav      (optional, used by zeroshot / abx)
        ground_truth.wav   (optional, used as upper-bound reference)
        <system_name>.wav  (one per system, e.g. VoxCPM2.wav)
        meta.json          (optional, see below)

For ABX panels each sample directory should contain ``reference.wav``,
``A.wav`` and ``B.wav`` plus a ``meta.json`` describing the two systems
behind A and B.

The mapping from panel directory name to MOS dimensions is automatic but
can be overridden by placing a ``panel.yaml`` at
``data/audio/<panel_name>/panel.yaml``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml

logger = logging.getLogger(__name__)

AUDIO_EXTS = (".wav", ".flac", ".mp3", ".ogg", ".m4a")
RESERVED_NAMES = {"reference", "ref", "ground_truth", "gt", "groundtruth"}

# --------------------------------------------------------------------------- #
# Anonymisation                                                                #
# --------------------------------------------------------------------------- #
#
# To prevent leaking system identity through the audio URL we map every
# audio file path to an opaque token via SHA-1 of (process-local random
# salt + absolute path).  The same path always yields the same token
# inside one server process, but the salt changes every restart so the
# token cannot be reconstructed from outside.
#
# The frontend only ever sees ``/audio/<token>``; the server resolves
# the token to a path via :func:`resolve_token`.

_AUDIO_SALT = secrets.token_hex(16)
_AUDIO_TOKENS: Dict[str, Path] = {}
_AUDIO_TOKENS_LOCK = threading.Lock()


def _register_audio(path: Path) -> str:
    abs_path = str(path.resolve())
    digest = hashlib.sha1((_AUDIO_SALT + abs_path).encode("utf-8")).hexdigest()
    token = digest[:24]
    with _AUDIO_TOKENS_LOCK:
        _AUDIO_TOKENS[token] = path
    return token


def resolve_token(token: str) -> Optional[Path]:
    """Return the absolute path registered for ``token`` (or ``None``)."""
    with _AUDIO_TOKENS_LOCK:
        return _AUDIO_TOKENS.get(token)


# --------------------------------------------------------------------------- #
# Default panel templates (used when no panel.yaml is provided)               #
# --------------------------------------------------------------------------- #

DEFAULT_PANEL_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "zeroshot": {
        "type": "mos",
        "title": {"zh": "零样本语音克隆", "en": "Zero-shot Voice Cloning"},
        "description": {
            "zh": "请先收听 Reference，然后对每个系统给出 N-MOS 与 S-MOS。",
            "en": "Listen to the reference first, then rate N-MOS and S-MOS for each system.",
        },
        "need_reference": True,
        "need_instruction": False,
        "dimensions": [
            {
                "key": "n_mos",
                "name": {"zh": "自然度 N-MOS", "en": "Naturalness (N-MOS)"},
                "hint": {
                    "zh": "整体自然度、流畅度、是否接近真人。",
                    "en": "Overall naturalness and how close it sounds to a real person.",
                },
            },
            {
                "key": "s_mos",
                "name": {"zh": "相似度 S-MOS", "en": "Similarity (S-MOS)"},
                "hint": {
                    "zh": "与参考说话人的音色相似度。",
                    "en": "How similar the voice sounds to the reference speaker.",
                },
            },
        ],
    },
    "multilingual": {
        "type": "mos",
        "title": {"zh": "多语言合成", "en": "Multilingual Synthesis"},
        "description": {
            "zh": "对每个系统给出整体自然度 N-MOS。",
            "en": "Rate the overall naturalness (N-MOS) for each system.",
        },
        "need_reference": False,
        "need_instruction": False,
        "dimensions": [
            {
                "key": "n_mos",
                "name": {"zh": "自然度 N-MOS", "en": "Naturalness (N-MOS)"},
                "hint": {
                    "zh": "整体自然度、流畅度、是否接近母语人士发音。",
                    "en": "Overall naturalness and how close it sounds to a native speaker.",
                },
            }
        ],
    },
    "controllable": {
        "type": "mos",
        "title": {"zh": "可控生成", "en": "Controllable Generation"},
        "description": {
            "zh": "请阅读控制描述，然后对每个系统给出 N-MOS 与 I-MOS。",
            "en": "Read the control description, then rate N-MOS and I-MOS for each system.",
        },
        "need_reference": False,
        "need_instruction": True,
        "dimensions": [
            {
                "key": "n_mos",
                "name": {"zh": "自然度 N-MOS", "en": "Naturalness (N-MOS)"},
                "hint": {
                    "zh": "整体自然度、流畅度。",
                    "en": "Overall naturalness and fluency.",
                },
            },
            {
                "key": "i_mos",
                "name": {"zh": "指令跟随 I-MOS", "en": "Instruction Following (I-MOS)"},
                "hint": {
                    "zh": "是否准确执行控制指令（情绪、风格、角色等）。",
                    "en": "How faithfully the output follows the instruction.",
                },
            },
        ],
    },
    "abx": {
        "type": "abx",
        "title": {"zh": "ABX 偏好测试", "en": "ABX Preference Test"},
        "description": {
            "zh": "请先收听 Reference，然后比较 A、B 哪一个更接近 Reference / 更符合描述。",
            "en": "Listen to the reference, then choose whether A or B is closer to it / better fits the description.",
        },
        "need_reference": True,
        "need_instruction": False,
        "dimensions": [
            {
                "key": "preference",
                "name": {"zh": "偏好选择", "en": "Preference"},
                "type": "choice",
                "choices": [
                    {"value": "A", "label": {"zh": "更像 A", "en": "Prefer A"}},
                    {"value": "B", "label": {"zh": "更像 B", "en": "Prefer B"}},
                    {"value": "tie", "label": {"zh": "相近 / Tie", "en": "Tie"}},
                ],
            }
        ],
    },
    "cmos": {
        "type": "cmos",
        "title": {"zh": "C-MOS 对比评测", "en": "C-MOS Comparative Evaluation"},
        "description": {
            "zh": "请将各系统与基准系统进行比较，并给出 -3 到 3 的 C-MOS 分数。",
            "en": "Compare each system against the anchor system and rate C-MOS from -3 to 3.",
        },
        "need_reference": False,
        "need_instruction": False,
        "anchor_system": "VoxCPM2",
        "dimensions": [
            {
                "key": "cmos",
                "name": {"zh": "C-MOS", "en": "C-MOS"},
                "hint": {
                    "zh": "与基准系统相比：-3 明显更差，0 相近，+3 明显更好。",
                    "en": "Compared with the anchor system: -3 much worse, 0 similar, +3 much better.",
                },
            }
        ],
    },
}


# --------------------------------------------------------------------------- #
# Dataclasses                                                                  #
# --------------------------------------------------------------------------- #


@dataclass
class AudioFile:
    role: str  # 'reference', 'ground_truth' or a system name
    url: str  # http path served by FastAPI


@dataclass
class Sample:
    sample_id: str
    audio: List[AudioFile]  # all audios (reference / gt / systems)
    systems: List[str]  # subset of audio entries that need to be rated
    reference_url: Optional[str] = None
    ground_truth_url: Optional[str] = None
    text: Optional[str] = None
    instruction: Optional[str] = None
    language: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    # CMOS-specific
    anchor_system: Optional[str] = None
    anchor_url: Optional[str] = None
    # ABX-specific
    abx_a_system: Optional[str] = None
    abx_b_system: Optional[str] = None


@dataclass
class Panel:
    name: str
    type: str  # 'mos' or 'abx'
    title: Dict[str, str]
    description: Dict[str, str]
    dimensions: List[Dict[str, Any]]
    samples: List[Sample]
    need_reference: bool = False
    need_instruction: bool = False


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def _audio_url(audio_path: Path) -> str:
    """Return the HTTP URL the frontend should use to fetch this audio.

    The URL is an opaque token rather than the real on-disk path, so the
    file name (and therefore the system name) is never revealed to the
    listener through devtools, the audio element ``src``, or downloads.
    """
    return "/audio/" + _register_audio(audio_path)


def _load_meta(sample_dir: Path) -> Dict[str, Any]:
    for name in ("meta.json", "metadata.json"):
        p = sample_dir / name
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                logger.warning("invalid JSON in %s: %s", p, exc)
                return {}
    return {}


def _load_panel_config(panel_dir: Path, panel_name: str) -> Dict[str, Any]:
    cfg_file = panel_dir / "panel.yaml"
    template_key = panel_name.lower()
    base = DEFAULT_PANEL_TEMPLATES.get(template_key)
    if base is None:
        # heuristic match
        if "abx" in template_key or "preference" in template_key:
            base = DEFAULT_PANEL_TEMPLATES["abx"]
        elif "cmos" in template_key or "comparative" in template_key:
            base = DEFAULT_PANEL_TEMPLATES["cmos"]
        elif "multi" in template_key or "lang" in template_key:
            base = DEFAULT_PANEL_TEMPLATES["multilingual"]
        elif "control" in template_key or "instruct" in template_key:
            base = DEFAULT_PANEL_TEMPLATES["controllable"]
        else:
            base = DEFAULT_PANEL_TEMPLATES["zeroshot"]
    cfg: Dict[str, Any] = json.loads(json.dumps(base))  # deep copy
    if cfg_file.is_file():
        try:
            override = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
            cfg.update(override)
        except yaml.YAMLError as exc:
            logger.warning("invalid YAML in %s: %s", cfg_file, exc)
    return cfg


def _collect_audio(sample_dir: Path, audio_root: Path) -> Dict[str, Path]:
    """Return mapping of role/system name -> audio file path."""
    result: Dict[str, Path] = {}
    for entry in sample_dir.iterdir():
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in AUDIO_EXTS:
            continue
        role = entry.stem
        result[role] = entry
    return result


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #


def scan_panels(audio_root: Path) -> List[Panel]:
    """Walk ``audio_root`` and build a list of :class:`Panel`.

    Each first-level subdirectory of ``audio_root`` is treated as one panel.
    """
    if not audio_root.is_dir():
        logger.warning("audio root does not exist: %s", audio_root)
        return []

    panels: List[Panel] = []
    panel_dirs = sorted(p for p in audio_root.iterdir() if p.is_dir())
    for panel_dir in panel_dirs:
        cfg = _load_panel_config(panel_dir, panel_dir.name)
        samples = _scan_samples(panel_dir, audio_root, cfg)
        if not samples:
            logger.info("panel '%s' has no samples, skipping", panel_dir.name)
            continue
        panels.append(
            Panel(
                name=panel_dir.name,
                type=cfg.get("type", "mos"),
                title=cfg.get("title", {"zh": panel_dir.name, "en": panel_dir.name}),
                description=cfg.get("description", {"zh": "", "en": ""}),
                dimensions=cfg.get("dimensions", []),
                samples=samples,
                need_reference=bool(cfg.get("need_reference", False)),
                need_instruction=bool(cfg.get("need_instruction", False)),
            )
        )
    return panels


def _scan_samples(panel_dir: Path, audio_root: Path, cfg: Dict[str, Any]) -> List[Sample]:
    panel_type = cfg.get("type", "mos")
    samples: List[Sample] = []
    sample_dirs = sorted(d for d in panel_dir.iterdir() if d.is_dir())
    for sample_dir in sample_dirs:
        files = _collect_audio(sample_dir, audio_root)
        if not files:
            continue
        meta = _load_meta(sample_dir)

        audios: List[AudioFile] = []
        for role, path in files.items():
            audios.append(AudioFile(role=role, url=_audio_url(path)))

        reference_url = next(
            (a.url for a in audios if a.role.lower() in {"reference", "ref"}),
            None,
        )
        gt_url = next(
            (a.url for a in audios if a.role.lower() in {"ground_truth", "gt", "groundtruth"}),
            None,
        )

        if panel_type == "abx":
            a_url = next((a.url for a in audios if a.role.upper() == "A"), None)
            b_url = next((a.url for a in audios if a.role.upper() == "B"), None)
            if a_url is None or b_url is None:
                logger.warning("ABX sample missing A/B: %s", sample_dir)
                continue
            samples.append(
                Sample(
                    sample_id=sample_dir.name,
                    audio=audios,
                    systems=["A", "B"],
                    reference_url=reference_url,
                    text=meta.get("text"),
                    instruction=meta.get("instruction"),
                    language=meta.get("language"),
                    meta=meta,
                    abx_a_system=meta.get("system_a"),
                    abx_b_system=meta.get("system_b"),
                )
            )
            continue

        if panel_type == "cmos":
            anchor_system = cfg.get("anchor_system") or meta.get("anchor_system") or "VoxCPM2"
            anchor_audio = next((a for a in audios if a.role == anchor_system), None)
            if anchor_audio is None:
                logger.warning(
                    "CMOS sample missing anchor system '%s': %s",
                    anchor_system,
                    sample_dir,
                )
                continue
            systems = [
                a.role
                for a in audios
                if a.role.lower() not in RESERVED_NAMES and a.role != anchor_system
            ]
            systems.sort()
            if not systems:
                logger.warning("CMOS sample without comparable systems: %s", sample_dir)
                continue
            samples.append(
                Sample(
                    sample_id=sample_dir.name,
                    audio=audios,
                    systems=systems,
                    reference_url=reference_url,
                    ground_truth_url=gt_url,
                    text=meta.get("text"),
                    instruction=meta.get("instruction"),
                    language=meta.get("language"),
                    meta=meta,
                    anchor_system=anchor_system,
                    anchor_url=anchor_audio.url,
                )
            )
            continue

        # MOS panels: rateable roles = system names (exclude reference / gt)
        systems = [a.role for a in audios if a.role.lower() not in RESERVED_NAMES]
        systems.sort()
        if gt_url is not None and "ground_truth" not in {s.lower() for s in systems}:
            # ground truth is rated as a system column in the report so we
            # include it in the systems list, but use a stable name
            systems = ["ground_truth"] + systems
        if not systems:
            logger.warning("sample without rateable systems: %s", sample_dir)
            continue
        samples.append(
            Sample(
                sample_id=sample_dir.name,
                audio=audios,
                systems=systems,
                reference_url=reference_url,
                ground_truth_url=gt_url,
                text=meta.get("text"),
                instruction=meta.get("instruction"),
                language=meta.get("language"),
                meta=meta,
            )
        )
    return samples


def panel_to_dict(panel: Panel) -> Dict[str, Any]:
    return {
        "name": panel.name,
        "type": panel.type,
        "title": panel.title,
        "description": panel.description,
        "dimensions": panel.dimensions,
        "need_reference": panel.need_reference,
        "need_instruction": panel.need_instruction,
        "samples": [sample_to_dict(s) for s in panel.samples],
    }


def sample_to_dict(sample: Sample) -> Dict[str, Any]:
    return {
        "sample_id": sample.sample_id,
        "audio": [a.__dict__ for a in sample.audio],
        "systems": sample.systems,
        "reference_url": sample.reference_url,
        "ground_truth_url": sample.ground_truth_url,
        "text": sample.text,
        "instruction": sample.instruction,
        "language": sample.language,
        "meta": sample.meta,
        "anchor_system": sample.anchor_system,
        "anchor_url": sample.anchor_url,
        "abx_a_system": sample.abx_a_system,
        "abx_b_system": sample.abx_b_system,
    }


def get_data_root() -> Path:
    root = os.environ.get("MOS_EVAL_DATA_ROOT")
    if root:
        return Path(root).resolve()
    return Path(__file__).resolve().parent.parent / "data"
