"""Ensure the toll_processor root is at the front of sys.path for this test suite."""
import sys
import os

processor_root = os.path.join(os.path.dirname(__file__), "..")
if processor_root not in sys.path:
    sys.path.insert(0, os.path.abspath(processor_root))
