"""Root conftest.py — no-op at the root level.
Each service test directory has its own conftest.py that adds the correct
service root to sys.path, preventing the two 'app' packages from colliding."""
