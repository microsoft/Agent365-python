# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Microsoft Agent 365 Tooling Extensions namespace package.

This file enables the `microsoft_agents_a365.tooling.extensions` namespace
to span multiple installed packages (e.g., extensions-openai, extensions-agentframework).
"""

import sys
from pkgutil import extend_path

# Standard pkgutil-style namespace extension
__path__ = extend_path(__path__, __name__)

# For editable installs with custom finders, manually discover extension paths
for finder in sys.meta_path:
    if hasattr(finder, "find_spec"):
        try:
            spec = finder.find_spec(__name__, None)
            if spec is not None and spec.submodule_search_locations:
                for path in spec.submodule_search_locations:
                    if path not in __path__ and not path.endswith(".__path_hook__"):
                        __path__.append(path)
        except (ImportError, TypeError):
            # Some meta path finders may not support this namespace and can raise
            # ImportError or TypeError; ignore these and continue discovering paths.
            pass
