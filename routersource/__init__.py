"""Package routersource is a build-time drop-in: tools/genrouter.py
regenerates source.py, the one file in here whose contents ever
change, to point at whichever route-providing repo should back this
deployment. main.py's import of this package never changes.
"""
from routersource.source import register

__all__ = ["register"]
