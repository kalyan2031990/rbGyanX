"""AAPM TG-263 structure name aliases (H&N focus for TCIA HNSCC)."""

from __future__ import annotations

# TG-263 token -> normalised alias keys (from normalise_name)
TG263_ALIASES: dict[str, list[str]] = {
    "Parotid_L": ["parotidl", "parotidleft", "ltparotid", "parotid_l", "glndparotidl"],
    "Parotid_R": ["parotidr", "parotidright", "rtparotid", "parotid_r", "glndparotidr"],
    "Submandibular_L": ["submandl", "submandibularl", "submandibular_l", "glndsubmandl"],
    "Submandibular_R": ["submandr", "submandibularr", "submandibular_r", "glndsubmandr"],
    "SpinalCord": ["spinalcord", "cord", "spine", "sc"],
    "BrainStem": ["brainstem", "brain_stem", "brainstemprv"],
    "Larynx": ["larynx", "glottis"],
    "Esophagus": ["esophagus", "oesophagus", "eso"],
    "OralCavity": ["oralcavity", "oral_cavity", "mucosaoral"],
    "Cochlea_L": ["cochleal", "cochlea_l", "lcochlea"],
    "Cochlea_R": ["cochlear", "cochlea_r", "rcochlea"],
    "Mandible": ["mandible", "jaw", "mand"],
    "Lips": ["lips", "lip", "oral_lips"],
    "PharynxConstrictor": [
        "pharynxconstrictor",
        "constrictor",
        "pcm",
        "pharyngealconstrictor",
        "pharynxconstrictors",
    ],
    "PharynxConstrictor_S": ["constrictors", "pcm_s", "inferiorconstrictor"],
    "PharynxConstrictor_M": ["constrictorm", "middleconstrictor"],
    "PharynxConstrictor_I": ["constrictori", "inferiorconstrictor"],
}
