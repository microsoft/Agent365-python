# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""In-tree PEP 517 entry point that delegates to the shared build backend.

PEP 517 requires ``backend-path`` entries to stay inside the project source tree,
so each library loads this module via ``backend-path = ["."]``. Inside a repository
checkout it adds ``versioning/helper`` to ``sys.path`` and re-exports the shared
backend's hooks, so ``uv lock`` and ``uv build`` work without setting ``PYTHONPATH``.
Outside a checkout (for example, building a wheel from an extracted sdist), the
helper directory must still be supplied through ``PYTHONPATH``.

Keep this file identical across ``libraries/*``; tests enforce that.
"""

import sys
from pathlib import Path

_HELPER_DIR = Path(__file__).resolve().parent.parent.parent / "versioning" / "helper"
if (_HELPER_DIR / "build_backend.py").is_file() and str(_HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(_HELPER_DIR))

from build_backend import *  # noqa: E402, F403
from build_backend import __all__  # noqa: E402, F401
