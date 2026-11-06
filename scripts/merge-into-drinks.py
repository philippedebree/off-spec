"""Merge one-file-per-recipe YAML (e.g. scraper output) into content/drinks/.

    python scripts/merge-into-drinks.py path/to/recipes [content/drinks]

Each input file becomes a version of the drink named by its `compare_key`.
Its file name (without .yaml) becomes the version slug, i.e. its URL /recipes/<slug>.
Re-running replaces versions with the same slug; nothing else is touched.
"""
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drinks_io import merge  # noqa: E402


def main(src, dest="content/drinks"):
    records = []
    for f in sorted(os.listdir(src)):
        if f.endswith((".yaml", ".yml")):
            with open(os.path.join(src, f), encoding="utf-8") as fh:
                rec = yaml.safe_load(fh)
            rec["_slug"] = os.path.splitext(f)[0]
            records.append(rec)
    written = merge(records, dest)
    print(f"{len(records)} recipes merged into {len(written)} drink files in {dest}")


if __name__ == "__main__":
    main(*sys.argv[1:])
