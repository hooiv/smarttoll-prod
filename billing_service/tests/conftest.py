"""Ensure the billing_service root is at the front of sys.path for this test suite."""
import sys
import os

billing_root = os.path.join(os.path.dirname(__file__), "..")
if billing_root not in sys.path:
    sys.path.insert(0, os.path.abspath(billing_root))
