# diagnostics_jobs/services/utils.py
import json

def pretty_print_json(data):
    """Segédeszköz a JSON szépen formázott kiírására"""
    print(json.dumps(data, indent=2, ensure_ascii=False))
