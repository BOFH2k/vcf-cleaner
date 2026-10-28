import importlib.util
from pathlib import Path


def load_cleaner():
    script = Path(__file__).resolve().parents[1] / "vcf-cleaner.py"
    spec = importlib.util.spec_from_file_location("vcf_cleaner", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
