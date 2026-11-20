"""The methods under comparison. Each is a trigger + a deadline rule + an
action rule, so the matrix is explicit rather than buried in the sim."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Method:
    key: str
    label: str
    trigger: str          # 'scaled' | 'raw' | 'threshold' | 'level' | 'time'
    deadline: str         # 'urgency' | 'fixed'
    action: str           # 'mc' | 'always_tx'
    trigger_level: float = None   # None -> use config default


METHODS = {
    "proposed":   Method("proposed", "Proposed (surprise + consequence)",
                         "combined", "urgency", "mc"),
    "fixed_dl":   Method("fixed_dl", "B5 fixed deadline",
                         "combined", "fixed", "mc"),
    "threshold":  Method("threshold", "B2 threshold alarm (no GP trigger)",
                         "threshold", "fixed", "mc", trigger_level=0.0),
    "threshold_dec": Method("threshold_dec",
                            "B2d decoupled threshold alarm (free level)",
                            "level", "fixed", "mc", trigger_level=0.35),
    "time_urg":   Method("time_urg", "B3 time-based urgency",
                         "time", "urgency", "mc", trigger_level=2.0),
    "always_tx":  Method("always_tx", "B1 always transmit in place",
                         "combined", "urgency", "always_tx"),
    "surprise_abl": Method("surprise_abl", "Ablation: surprise only (no consequence)",
                           "surprise", "urgency", "mc", trigger_level=1.9),
    "raw_abl":    Method("raw_abl", "Ablation: raw error (no uncertainty scaling)",
                         "raw", "urgency", "mc", trigger_level=0.55),
}

MAIN_FIVE = ["proposed", "fixed_dl", "threshold", "time_urg", "always_tx"]
ABLATIONS = ["surprise_abl", "raw_abl"]
ALL_KEYS = MAIN_FIVE + ABLATIONS
# Every method builds a cloud GP map; only the TRIGGER differs. These are the
# ones whose trigger consults the GP:
GP_TRIGGER_KEYS = ["proposed", "fixed_dl", "always_tx", "surprise_abl", "raw_abl"]
NON_GP_TRIGGER_KEYS = ["threshold", "time_urg"]
# Not in ALL_KEYS: this is a follow-up baseline added after the main programme
# (E14) and adding it there would change what every earlier check compares.
DECOUPLED = ["threshold_dec"]
