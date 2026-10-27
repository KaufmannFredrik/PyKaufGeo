"""Entry point: ``python -m pykaufgeo``."""

import sys

from pykaufgeo.gui.app import run

if __name__ == "__main__":
    sys.exit(run(sys.argv))
