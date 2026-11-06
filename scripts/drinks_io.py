"""Read, merge and write per-drink YAML files (content/drinks/<compare_key>.yaml).

File shape:

    name: Mai Tai
    tags: [mai-tai, tiki]
    related: [...]
    versions:
      - slug: mai-tai-garrett-richards     # URL: /recipes/<slug>
        name: Mai Tai (1956)               # only when it differs from the drink name
        method: shaken
        ...                                # every other recipe field

A flat recipe record (one per version, as the scraper and importer produce) has
`compare_key`, `tags` and `related` at its top level; those move to the drink.
"""
import os
import yaml

DRINK_LEVEL = ("compare_key", "tags", "related")

# Display names for drinks whose versions are all named differently.
DRINK_NAMES = {
    "mai-tai": "Mai Tai",
    "margarita": "Margarita",
    "daiquiri": "Daiquiri",
}


class _Dumper(yaml.SafeDumper):
    pass


def _str(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


class _Flow(dict):
    """Rendered on one line: {name: Lime juice, ml: 30, oz: 1, scaling: linear}."""


_Dumper.add_representer(str, _str)
_Dumper.add_representer(
    _Flow, lambda d, data: d.represent_mapping("tag:yaml.org,2002:map", data.items(), flow_style=True))


def load_drink(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def write_drink(path, drink):
    for v in drink["versions"]:
        if "ingredients" in v:
            v["ingredients"] = [_Flow(i) for i in v["ingredients"]]
    n = len(drink["versions"])
    header = f"# {drink['name']} - {n} version{'s' if n != 1 else ''}\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        yaml.dump(drink, f, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=200)


def to_version(rec, slug):
    """Flat recipe record -> version entry (drink-level fields removed)."""
    v = {"slug": slug}
    v.update({k: val for k, val in rec.items() if k not in DRINK_LEVEL})
    return v


def _finish(key, name, tags, related, versions):
    name = name or DRINK_NAMES.get(key) or next((v["name"] for v in versions if v.get("name")), key)
    out = {"name": name}
    tags = sorted(set(tags))
    related = sorted(set(related) - {key})
    if tags:
        out["tags"] = tags
    if related:
        out["related"] = related
    clean = []
    for v in versions:
        v = dict(v)
        ordered = {"slug": v.pop("slug")}
        vname = v.pop("name", None) or name
        if vname != name:
            ordered["name"] = vname
        ordered.update(v)
        clean.append(ordered)
    out["versions"] = clean
    return out


def merge(records, drinks_dir, drop=None):
    """Merge flat recipe records (each with '_slug' or 'slug') into per-drink files.

    A version whose slug already exists is replaced in place; new ones are appended.
    `drop(version) -> bool` first removes matching existing versions (e.g. a previous
    import from the same source), and drink tags/related are then rebuilt from what remains.
    Returns {compare_key: version_count} for the drinks that were written.
    """
    os.makedirs(drinks_dir, exist_ok=True)
    incoming = {}
    for rec in records:
        rec = dict(rec)
        slug = rec.pop("_slug", None) or rec.pop("slug")
        key = rec["compare_key"]
        incoming.setdefault(key, []).append((to_version(rec, slug), rec.get("tags") or [], rec.get("related") or []))

    keys = set(incoming)
    if drop:
        for f in os.listdir(drinks_dir):
            if f.endswith(".yaml") and f[:-5] not in keys:
                if any(drop(v) for v in load_drink(os.path.join(drinks_dir, f)).get("versions", [])):
                    keys.add(f[:-5])

    written = {}
    for key in sorted(keys):
        path = os.path.join(drinks_dir, key + ".yaml")
        drink = load_drink(path) if os.path.exists(path) else {}
        kept = [v for v in drink.get("versions", []) if not (drop and drop(v))]
        new = {v["slug"]: v for v, _, _ in incoming.get(key, [])}
        merged = [new.pop(v["slug"], v) for v in kept] + list(new.values())
        if not merged:
            os.remove(path)
            continue
        tags = [t for _, ts, _ in incoming.get(key, []) for t in ts]
        related = [r for _, _, rs in incoming.get(key, []) for r in rs]
        if kept or not drop:  # versions from other sources remain: keep the drink's existing tags
            tags += drink.get("tags") or []
            related += drink.get("related") or []
        write_drink(path, _finish(key, drink.get("name"), tags, related, merged))
        written[key] = len(merged)
    return written
