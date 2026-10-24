"""RegLens - CHANGE ME."""

import os

# Keep CLI output clean and start-up offline-safe.
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

__version__ = "0.1.0"
