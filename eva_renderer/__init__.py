"""Automated DXF renderer for premium EVA car mat product visuals."""

__version__ = "0.7.8"

from .batch import BatchConfig, JobResult, run_batch, run_batch_detailed

__all__ = ["BatchConfig", "JobResult", "run_batch", "run_batch_detailed", "__version__"]
