from pathlib import Path

import yaml


def load_prompts(prompts_py: str) -> dict[str, str]:
    """Load the `prompts.yaml` that sits next to a feature's `prompts.py` (pass `__file__`)."""
    return yaml.safe_load(Path(prompts_py).with_name("prompts.yaml").read_text(encoding="utf-8"))
