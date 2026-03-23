import sys
import os

sys.path.insert(0, "C:\WK\pynamespace\aiagent")

try:
    from template.src.template import main
    print("Successfully imported template.src.template.main")
except ImportError as e:
    print(f"ImportError: {e}")
    print("sys.path:", sys.path)
