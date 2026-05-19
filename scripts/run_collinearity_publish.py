from __future__ import annotations

import sys

from nde_analysis.cli import main


if __name__ == "__main__":
    sys.argv = [
        "nde-analysis",
        "run-collinearity",
        "--config",
        "configs/collinearity_publish.yaml",
    ]
    main()
