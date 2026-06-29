# -----------------------------------------------------------------------------
# backend/app/ai/generators/__init__.py
#
# Public surface of the generators sub-package. Import SyntheticDataGenerator
# from here rather than from the implementation module directly so internal
# refactors don't break callers.
# -----------------------------------------------------------------------------

from app.ai.generators.synthetic_data_generator import SyntheticDataGenerator

__all__ = ["SyntheticDataGenerator"]
