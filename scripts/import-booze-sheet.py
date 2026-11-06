"""Import the Booze Google Sheet (Cocktails to Try, Tiki!, Mai Tai and Margaritas tabs) into content/drinks/.

Export the sheet as .xlsx (File > Download > Microsoft Excel), then:
    pip install openpyxl pyyaml
    python scripts/import-booze-sheet.py Booze.xlsx content/drinks

Re-running replaces every version that came from the sheet and leaves versions from
other sources (e.g. the Punch/Difford's scraper) untouched.
"""
import re, sys, datetime, json
from fractions import Fraction
import openpyxl
import yaml

SHEET_URL = "https://docs.google.com/spreadsheets/d/1oQFek7K0r7irm5O5_NQaWkocgF5-u_JsTv_SAaRo-TY"
RETRIEVED = "2026-11-06"
OZ_ML = 30  # site convention: 1 oz = 30 ml
TSP_ML = 5

# ---------------------------------------------------------------- helpers

def slugify(s):
    s = s.lower().replace("&", "and").replace("é", "e").replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

def num(s):
    """'1 1/2' / '3/4' / '.75' / '1.5' -> float"""
    s = s.strip()
    total = 0.0
    for part in s.split():
        total += float(Fraction(part)) if "/" in part else float(part)
    return total

NUM = r"(?:\d+\s+\d+/\d+|\d+/\d+|\d*\.\d+|\d+)"

STRONG = re.compile(r"absinthe|fernet|green chartreuse|peated|islay|creme de menthe|crème de menthe|habanero|hot sauce|pimento|allspice|ancho|saline", re.I)

def clean_oz(x):
    return round(x, 3)

def ing_volume(name, oz, **extra):
    ml = oz * OZ_ML
    ml = round(ml * 2) / 2 if ml >= 5 else round(ml, 2)
    if ml == int(ml):
        ml = int(ml)
    d = {"name": name, "ml": ml, "oz": clean_oz(oz), "scaling": "linear"}
    if STRONG.search(name) and ml <= 15:
        d["round"] = "down"
    d.update(extra)
    return d

def ing_dash(name, n, unit="dash"):
    n_int = int(n) if float(n) == int(n) else n
    label = f"{n_int} {unit}{'es' if unit == 'dash' and n != 1 else ('s' if unit != 'dash' and n != 1 else '')}"
    if unit == "dash":
        return {"name": name, "dashes": n_int, "amount": label, "scaling": "dash"}
    return {"name": name, "amount": label, "scaling": "dash"}

def ing_fixed(name, amount, scaling="fixed"):
    return {"name": name, "amount": amount, "scaling": scaling}

# ---------------------------------------------------------- name normalising

NAME_MAP = [
    (r"^ginm$", "Gin"),
    (r"^yellow c$", "Yellow Chartreuse"), (r"^green c$", "Green Chartreuse"),
    (r"chartru?e?use", "Chartreuse"),
    (r"^bene$", "Bénédictine"), (r"^benedictine$", "Bénédictine"),
    (r"^ango$|^aromatic$|^angostura$|^angostura bitters$", "Angostura bitters"),
    (r"^peychauds?$|^peychaud'?s bitters$|^pechaud'?s bitters$", "Peychaud's bitters"),
    (r"^orange$", "Orange bitters"),
    (r"^oj$", "Orange juice"),
    (r"^simple$|^simple syrup$", "Simple syrup"),
    (r"^lemon$|^lemon juice.*$", "Lemon juice"),
    (r"^li+me$|^lime juice.*$", "Lime juice"),
    (r"^grapefruit juice$", "Grapefruit juice"),
    (r"^pineapple$", "Pineapple juice"),
    (r"^grenadine$", "Grenadine"),
    (r"^orgeat$", "Orgeat"),
    (r"vremouth", "vermouth"), (r"liq[ue]+ue?r", "liqueur"), (r"liquer", "liqueur"),
    (r"^genepy$", "Génépy"), (r"^strega$", "Strega"),
    (r"^italicus$", "Italicus"), (r"^curacao$", "Curaçao"), (r"curacao", "curaçao"),
    (r"^cream$", "Cream"), (r"^blanco$", "Blanc vermouth"),
    (r"vanila", "vanilla"),
]

def norm_name(n):
    n = re.sub(r"\s+", " ", n.strip(" ,.-"))
    n = re.sub(r"^(?:oz|ounces?|fl oz)\s+", "", n, flags=re.I)
    for pat, rep in NAME_MAP:
        if re.search(pat, n, re.I):
            if pat.startswith("^"):
                n = rep
            else:
                n = re.sub(pat, rep, n, flags=re.I)
    n = re.sub(r",?\s*freshly squeezed", "", n, flags=re.I)
    return n[0].upper() + n[1:] if n else n

# ----------------------------------------------------- free-text spec parser

def parse_item(raw):
    """Parse one comma-separated item from the 'Recipe' column."""
    t = raw.strip()
    if not t:
        return None
    low = t.lower()
    if low.startswith("top with") or low.startswith("top "):
        rest = re.sub(r"^top( with)?\s*", "", t, flags=re.I)
        m = re.match(rf"({NUM})(?:-{NUM})?\s*(?:oz)?\s+(.*)", rest)
        if m:
            return {**ing_volume(norm_name(m.group(2)), num(m.group(1))), "scaling": "topper"}
        return ing_fixed(norm_name(rest), "top", "topper")
    if "rinse" in low:
        name = re.sub(r"rinse( glass)?", "", t, flags=re.I)
        return ing_fixed(norm_name(name), "rinse", "rinse")
    if re.search(r"egg white", t, re.I):
        return ing_fixed("Egg white", "1 egg white")
    # dashes / drops
    m = re.match(rf"({NUM})\s*(dash(?:es)?|drops?)\s+(.*)", t, re.I)
    if m:
        unit = "dash" if m.group(2).lower().startswith("dash") else "drop"
        return ing_dash(norm_name(m.group(3)), num(m.group(1)), unit)
    m = re.match(r"(dash|splash)\s+(.*)", t, re.I)
    if m:
        if m.group(1).lower() == "dash":
            return ing_dash(norm_name(m.group(2)), 1)
        return ing_fixed(norm_name(m.group(2)), "splash")
    # teaspoon / barspoon
    m = re.match(rf"({NUM})\s*(?:t|tsp)\s+(.*)", t, re.I)
    if m:
        oz = num(m.group(1)) * TSP_ML / OZ_ML
        d = ing_volume(norm_name(m.group(2)), oz)
        d["amount"] = f"{m.group(1)} tsp"
        return d
    m = re.match(rf"({NUM})?\s*bar\s*spoon\s+(.*)", t, re.I)
    if m:
        n = num(m.group(1)) if m.group(1) else 1
        d = ing_volume(norm_name(m.group(2)), n * TSP_ML / OZ_ML)
        d["amount"] = f"{m.group(1) or 1} barspoon"
        return d
    m = re.match(rf"({NUM})\s*ml\s+(.*)", t, re.I)
    if m:
        return ing_volume(norm_name(m.group(2)), num(m.group(1)) / OZ_ML)
    m = re.match(rf"({NUM}-{NUM})\s+(.*)", t)
    if m:
        return ing_fixed(norm_name(m.group(2)), m.group(1))
    # volume in oz (bare number = oz)
    m = re.match(rf"({NUM})\s*(?:fl\s*oz|oz|ounces?|ounce)?\.?\s*(?:\(\d+ml\))?\s+(.*)", t, re.I)
    if m:
        qty, name = num(m.group(1)), m.group(2)
        # count-based items
        if re.search(r"\b(leaves|leaf|slices?|grapes|wedges?|cubes?|tomatoes|wheels?)\b", name, re.I):
            return ing_fixed(norm_name(name), f"{m.group(1)}")
        return ing_volume(norm_name(name), qty)
    m = re.match(r"(\d+)ml\s+(.*)", t, re.I)
    if m:
        return ing_volume(norm_name(m.group(2)), int(m.group(1)) / OZ_ML)
    if re.search(r"egg white", t, re.I):
        return ing_fixed("Egg white", "1 egg white")
    return {"name": norm_name(t), "amount": "?", "scaling": "fixed", "_unparsed": True}

def parse_spec(text):
    text = text.replace("\u2044", "/").replace("\t", " ").replace(", freshly squeezed", "")
    parts = [p for p in re.split(r",\s*", text) if p.strip()]
    out = [parse_item(p) for p in parts]
    return [o for o in out if o]

# ----------------------------------------------------------- glass & method

GLASSES = [
    (r"nick", "nick-and-nora", "up"), (r"coupe|coup\b", "coupe", "up"),
    (r"flute", "flute", "up"), (r"glencairn", "glencairn", "up"),
    (r"rocks|old fashioned", "old-fashioned", "rocks"),
    (r"collins", "collins", "tall"), (r"highball", "highball", "tall"),
    (r"hurricane", "hurricane", "tall"), (r"pilsner", "pilsner", "tall"),
    (r"pearl diver", "pearl-diver", "crushed-ice"),
    (r"snifter", "snifter", "crushed-ice"), (r"tiki mug|mug", "tiki-mug", "crushed-ice"),
]

def find_glass(text):
    if not text:
        return None
    for pat, g, served in GLASSES:
        if re.search(pat, text, re.I):
            return g, served
    return None

def split_garnish(text):
    """'Lemon twist // Rocks' -> ('Lemon twist', 'Rocks')"""
    if not text:
        return None, None
    text = str(text).strip()
    if "//" in text:
        g, glass = [x.strip() for x in text.split("//", 1)]
        return (g or None), glass
    if find_glass(text) and not re.search(r"twist|peel|wheel|leaf|sprig|cherry|nutmeg", text, re.I):
        return None, text
    return text.rstrip(", "), None

SHAKE_HINT = re.compile(r"juice|lemon|lime|egg|cream|milk|orgeat.*lemon|pineapple|grapefruit|passion|puree|oj\b", re.I)

# ----------------------------------------------------------- source mapping

def map_source(raw):
    """Return (site, credit)."""
    if not raw:
        return None, None
    r = str(raw).strip()
    table = {
        "punch drink": ("Punch", None), "punch": ("Punch", None),
        "difford's": ("Difford's Guide", None), "liquor.com": ("Liquor.com", None),
        "educated barfly": ("The Educated Barfly", None),
        "thirstywhale_ // employees only nyc": ("@thirstywhale_ (Instagram)", "Employees Only, NYC"),
        "she_thebartender": ("@she_thebartender (Instagram)", None),
        "pusser's insta": ("Pusser's (Instagram)", None),
        "notjustabartender": ("@notjustabartender (Instagram)", None),
        "rum fire insta": ("Rum Fire (Instagram)", None),
        "anders erickson": ("Anders Erickson", None),
        "distinguished spirits/adapted from trader vic": ("Distinguished Spirits", "Adapted from Trader Vic"),
        "distinguished spirits": ("Distinguished Spirits", None),
        "beachbum berry": ("Beachbum Berry", None), "beachbum": ("Beachbum Berry", None),
        "make and drink/trader vic": ("Make and Drink", "Trader Vic"),
        "distinguished spirits / don the beachcomber": ("Distinguished Spirits", "Don the Beachcomber"),
        "smuggler's cove": ("Smuggler's Cove", None),
        "sippin safari (beachbum)": ("Sippin' Safari", "Jeff \"Beachbum\" Berry"),
        "breezeway / hurricane hayward": ("The Atomic Grog", "Hurricane Hayward, after the Mai-Kai"),
        "don the beachcomber": ("Don the Beachcomber", None),
        "make and drink / mai kai": ("Make and Drink", "The Mai-Kai"),
        "don the beachcomber/smugglers's cove": ("Smuggler's Cove", "Don the Beachcomber"),
        "don the beachcomber/smuggler's cove": ("Smuggler's Cove", "Don the Beachcomber"),
        "make and drink/trader sam's": ("Make and Drink", "Trader Sam's"),
        "distinguished spirits/mai kai": ("Distinguished Spirits", "The Mai-Kai"),
        "joe scailom (egypt!)": ("Joe Scialom", "Shepheard's Hotel, Cairo"),
        "https://subtletiki.com/": ("Subtle Tiki", None),
        "distinguished spirits/don the beachcomber": ("Distinguished Spirits", "Don the Beachcomber"),
        "hamilton/tiki book/general": ("Traditional", None),
        "sam ross (inventor of the penicillin)": ("Sam Ross", None),
        "steve the bartender": ("Steve the Bartender", None),
        "make and drink / beachbum berry": ("Make and Drink", "Jeff \"Beachbum\" Berry"),
    }
    return table.get(r.lower(), (r, None))

def source_slug(site):
    if not site:
        return "house"
    s = site.lower()
    for k, v in [("punch", "punch"), ("difford", "diffords"), ("educated barfly", "educated-barfly"),
                 ("smuggler", "smugglers-cove"), ("distinguished", "distinguished-spirits"),
                 ("make and drink", "make-and-drink"), ("beachbum", "beachbum-berry"),
                 ("sippin", "beachbum-berry")]:
        if k in s:
            return v
    return slugify(site.replace("(Instagram)", "").replace("@", ""))

# ------------------------------------------------------ ingredient tidy-up

RENAME = {
    "Irish": "Irish whiskey", "Jamaican": "Jamaican rum", "Pussers": "Pusser's rum",
    "Smith and Cross": "Smith & Cross Jamaican rum", "Cuban/Puerto Rican Style": "Cuban/Puerto Rican-style rum",
    "Stiggins Fancy": "Stiggins' Fancy pineapple rum", "Gran Marnier": "Grand Marnier",
    "Soda": "Soda water", "Club soda": "Soda water", "Agave": "Agave syrup", "Saline": "Saline solution",
    "Saline Solution": "Saline solution", "Saline Solution 20%": "Saline solution (20%)",
    "Jamaica Rum": "Jamaican rum", "Jamaican Rum": "Jamaican rum", "Blanc vermouth": "Blanc vermouth",
    "Creme de menthe": "Crème de menthe", "Amaro": "Amaro", "Whiskey": "American whiskey",
    "Cocchi americano": "Cocchi Americano", "Blended scotch": "Blended Scotch", "Tequila Reposado": "Reposado tequila",
    "Aged Jamaican": "Aged Jamaican rum", "Pot still irish whiskey": "Pot-still Irish whiskey", "Hot Honey": "Hot honey",
    "Pineapple simple": "Pineapple syrup", "Mint tea simple": "Mint tea syrup", "Passionfruit puree": "Passionfruit purée",
    "Ramazzoti amaro": "Ramazzotti", "Ramazzoti": "Ramazzotti", "Chamomile infused rye": "Chamomile-infused rye",
    "Orange Juice": "Orange juice", "Heavy Cream": "Heavy cream",
}

GENERIC = {"whiskey", "whisky", "bitters", "rum", "juice", "syrup", "liqueur", "vermouth", "cream", "gin", "wine",
           "water", "sugar", "cube", "solution", "garnish", "wheel", "wedges", "leaves", "slices", "brandy", "tequila",
           "lager", "dry", "london", "heavy", "white", "orange", "lemon", "blended", "reposado", "espadin", "rich", "demerara"}

RENAME_NOTE = {
    "Clement Creole Shurbb": ("Clément Créole Shrubb", None),
    "Acid Adjusted Pineapple juice": ("Acid-adjusted pineapple juice", None),
    "Coruba Dark Jamaica rum": ("Dark Jamaican rum", "Coruba"),
    "Chairman's Reserve Saint Lucia rum": ("St Lucia rum", "Chairman's Reserve"),
    "Appleton 12 rum": ("Aged Jamaican rum", "Appleton 12"),
    "Smith & Cross rum": ("Overproof Jamaican rum", "Smith & Cross"),
    "Plantation OFTD rum": ("Overproof dark rum", "Plantation OFTD"),
    "Plantation rum O.F.T.D. Overproof": ("Overproof dark rum", "Plantation OFTD"),
    "Plantation Xaymaca rum": ("Jamaican rum", "Plantation Xaymaca"),
    "Bacardi Select/Black rum": ("Dark rum", "Bacardi Select or Black"),
    "Bacardi Gold rum": ("Gold rum", "Bacardi Gold"),
    "Lemon Hart 151 rum": ("Overproof Demerara rum", "Lemon Hart 151"),
    "Hamilton 114 rum": ("Overproof Demerara rum", "Hamilton 114"),
    "Dark rum or dark demerara rum": ("Dark rum", "or dark Demerara rum"),
    "Trader Vic's Gold rum": ("Gold rum", "Trader Vic's"),
    "Trader Vic's Light rum": ("Light rum", "Trader Vic's"),
    "Lightly Aged Puerto Rican rum": ("Lightly aged Puerto Rican rum", None),
    "Stiggins Pineapple rum": ("Pineapple rum", "Stiggins' Fancy"),
    "Plantation rum Stiggins's Fancy": ("Pineapple rum", "Stiggins' Fancy"),
    "BG Reynolds Orgeat": ("Orgeat", "BG Reynolds"),
    "BG Reynolds Pineapple Molasses syrup": ("Pineapple molasses syrup", "BG Reynolds"),
    "Orgeat syrup": ("Orgeat", None), "Orange curaçao liqueur": ("Orange curaçao", None),
    "Orange Curaçao": ("Orange curaçao", None), "Curaçao": ("Orange curaçao", None),
    "Fresh Lime juice": ("Lime juice", None), "Fresh squeezed lime juice": ("Lime juice", None),
    "Martinique Molasses Rhum": ("Martinique molasses rhum", None),
    "Rhum Agricole Blanc": ("Rhum agricole blanc", None),
    "Pierre Ferrand dry curaçao": ("Dry curaçao", "Pierre Ferrand"),
    "Ferrand dry curaçao": ("Dry curaçao", "Pierre Ferrand"),
    "Rock Candy syrup": ("Rock candy syrup", None),
    "Don's Spices No. 2": ("Don's Spices #2", None),
}

def tidy(ing):
    ing["name"] = ing["name"].replace("’", "'")
    name = ing["name"]
    m = re.match(r"(.*?)\s*\(([^)]*)\)\s*(.*)$", name)
    if m and not ing.get("_unparsed"):
        base, paren, rest = m.group(1), m.group(2), m.group(3)
        if paren and re.fullmatch(r"\d+:\d+", paren):
            name = f"{base} ({paren})"
        else:
            name = (base + " " + rest).strip()
            ing["note"] = paren if not ing.get("note") else ing["note"] + "; " + paren
    if re.search(r"\bfloat\b", name, re.I):
        name = re.sub(r"\s*\bfloat\b", "", name, flags=re.I).strip()
        ing["note"] = (ing.get("note", "") + "; float").strip("; ")
    for pat, nm, note in [(r"^Mezcal Espadin$", "Mezcal", "espadín"), (r"^Blended Rum Banks 7 Island$", "Blended rum", "Banks 7 Island"),
                          (r"^Thin slice fresno$", "Fresno chile", None)]:
        if re.match(pat, name, re.I):
            name = nm
            if note: ing["note"] = note
            if nm == "Fresno chile": ing["amount"] = "1 thin slice"
    pm = re.search(r"\s+(\d+)\s+proof$", name, re.I)
    if pm:
        name = name[:pm.start()]
        ing["note"] = (ing.get("note", "") + f"; {pm.group(1)} proof").strip("; ")
    name = RENAME.get(name, name)
    rn = {k.lower().replace("’", "'"): v for k, v in RENAME_NOTE.items()}
    if name.lower() in rn:
        name, extra_note = rn[name.lower()]
        if extra_note:
            ing["note"] = extra_note + ("; " + ing["note"] if ing.get("note") else "")
        ing["name"] = name
        return ing
    words = name.split(" ")
    words = [w if i == 0 or w.lower() not in GENERIC else w.lower() for i, w in enumerate(words)]
    name = " ".join(words)
    ing["name"] = name[0].upper() + name[1:]
    if isinstance(ing.get("oz"), float) and ing["oz"] == int(ing["oz"]):
        ing["oz"] = int(ing["oz"])
    if STRONG.search(ing["name"]) and ing.get("ml") is not None and ing["ml"] <= 15 and ing["scaling"] == "linear":
        ing["round"] = "down"
    return ing

V = ing_volume
D = ing_dash
F = ing_fixed

def T(name, oz=None, amount="top"):
    """Topper."""
    if oz is None:
        return F(name, amount, "topper")
    return {**V(name, oz), "scaling": "topper"}

# Rows the parser can't read cleanly ('Cocktails to Try', by sheet row number).
CTT_OVERRIDES = {
    3: dict(ings=[V("Lemon juice", 1.5), V("Absinthe", 0.75), V("Simple syrup", 0.75)],
            method="swizzled", steps=["Whip-shake, then swizzle over crushed ice."]),
    5: dict(ings=[V("Amaretto", 2), V("Lemon juice", 1), F("Egg white", "1 egg white"),
                  T("Red wine", amount="float", ) | {"note": "Malbec; float over a barspoon"}],
            garnish="8 drops Angostura bitters"),
    20: dict(ings=[V("Gin", 0.75), V("Cognac", 0.75), V("Rye whiskey", 0.75), V("Sweet vermouth", 0.75),
                   D("Orange bitters", 2)]),
    22: dict(ings=[V("Cream", 1), V("Crème de cacao (light)", 1), V("Galliano", 1)],
             review="Written as equal parts; set to 1 oz each."),
    25: dict(ings=[V("Gin", 2), V("Lemon juice", 0.75), V("Orgeat", 0.75), D("Angostura bitters", 2),
                   ing_dash("Saline solution", 5, "drop")]),
    29: dict(ings=[V("London Dry gin", 0.75), V("Campari", 0.75), V("Bianco vermouth", 0.75), V("Grand Marnier", 0.5)],
             garnish="Drop of rose essential oil"),
    30: dict(ings=[V("Gin", 1.5), V("Absinthe", 0.25), V("Green Chartreuse", 0.25) | {"note": "lit on fire"},
                   V("Lemon juice", 0.75), V("Simple syrup", 0.75), F("Egg white", "1 egg white")]),
    32: dict(steps=["Smoke a rosemary sprig under the overturned coupe before pouring."], drop=["Smoke rosemary"]),
    33: dict(replace={"Absinthe float": F("Absinthe", "float")}),
    34: dict(replace={"Club soda to top": T("Soda water"), "Sugar": V("Sugar", 0.5 * TSP_ML / OZ_ML) | {"amount": "1/2 tsp"}}),
    36: dict(replace={"Soda water": T("Soda water"), "Cucumber slices": F("Cucumber slices", "3") | {"note": "muddled"}}),
    37: dict(ings=[V("Gin", 0.75), V("Stiggins' Fancy pineapple rum", 0.75),
                   V("Lilletperitif", 0.5) | {"note": "house blend: Lillet, Cynar, Campari at 1 : 0.5 : 0.25"},
                   V("Honey syrup", 0.25), V("Lemon juice", 0.25), V("Lime juice", 0.25)]),
    44: dict(ings=[V("Lime juice", 0.5), F("Orange juice", "splash"), F("Coconut cream", "1 spoonful"),
                   T("Soda water"), F("Vanilla Angostura bitters", "float")],
             name="Untitled (she_thebartender)"),
    48: dict(replace={"White rum": V("White rum", 2)}),
    49: dict(replace={"White Rum": V("White rum", 1.5)}),
    50: dict(ings=[V("Sweet vermouth", 1), V("Campari", 1), V("Rum", 1)],
             review="Written as 1:1:1; set to 1 oz each."),
    52: dict(ings=[V("Pimento dram", 0.5), V("Demerara rum", 1.5) | {"note": "86 Co. Demerara"}, T("Orange juice", amount="fill")],
             review="Written as 1 part pimento dram to 3 parts rum; set to 0.5 / 1.5 oz."),
    58: dict(ings=[V("Overproof Jamaican rum", 0.75) | {"note": "Rum Fire"}, V("Yellow Chartreuse", 0.75),
                   V("Aperol", 0.75), V("Lime juice", 0.75)],
             review="Written as 1:1:1:1; set to 0.75 oz each (the usual equal-parts pour)."),
    59: dict(replace={"Splash Soda Water": F("Soda water", "splash"), "Rough Cut Sugar Cube": F("Sugar cube (rough cut)", "1")}),
    60: dict(replace={"White rum": V("White rum", 1)}),
    63: dict(replace={"Sparkling wine to top": T("Sparkling wine")}),
    65: dict(ings=[V("Blanco tequila", 1),
                   V("Cranberry shrub", 1.5) | {"note": "equal parts cranberry juice, water, white vinegar and white sugar"}],
             review="Spec looks incomplete (trailing comma in the sheet)."),
    69: dict(replace={"Absinthe mist overtop": F("Absinthe", "mist over the top", "rinse")}),
    79: dict(replace={"Soda Water": F("Soda water", "1 dash")}),
    80: dict(ings=[F("Orange wheel", "1/2") | {"note": "muddled"}, V("Heavy cream", 1),
                   ing_dash("Saline solution (20%)", 5, "drop"), V("White crème de cacao", 1), V("Fernet-Branca", 1.5)]),
    84: dict(drop=["Cocktail Cherry Garnish"], garnish="Cocktail cherry"),
    85: dict(replace={"Pinch of Dill": F("Dill", "pinch")}, compare_key="accidental-tourist"),
    93: dict(replace={"White Rum": V("White rum", 1)}),
    95: dict(ings=[V("Oak-aged gin", 1), V("Italian red bitter liqueur", 0.75), V("Strucchi dry vermouth", 0.75),
                   V("Italicus", 0.25)]),
    64: dict(replace={"Scotch": V("Scotch", 1.5) | {"note": "lightly peated"}}),
    43: dict(replace={"Mexican lager": T("Mexican lager", 2)}),
    51: dict(),
    78: dict(name="Untitled (bourbon & brandy sour)", review="Unnamed in the sheet; 'vermouth' unspecified (sweet or dry)."),
}

COMPARE_KEY = {
    "Deke Dunne's Widow's Kiss": "widows-kiss", "Cane and Table's Royal Hawaiian": "royal-hawaiian",
    "Dauphine's Roffignac": "roffignac", "Pusser's Hurricane": "hurricane", "Al Sotack's Brainstorm": "brainstorm",
    "Nui Nui/Pupule": "nui-nui", "Pain Killada": "painkillada",
}

def compare_key(name):
    if name in COMPARE_KEY:
        return COMPARE_KEY[name]
    k = slugify(name)
    return re.sub(r"^the-", "", k)

def infer_method(ings, spec_text=""):
    names = " ".join(i["name"] for i in ings).lower()
    if "sugar cube" in names:
        return "built"
    has_top = any(i["scaling"] == "topper" for i in ings)
    linear = [i for i in ings if i["scaling"] == "linear"]
    if "swizzle" in spec_text.lower():
        return "swizzled"
    if SHAKE_HINT.search(names):
        return "shaken"
    if has_top and len(linear) <= 2:
        return "built"
    return "stirred"

def default_glass(method, ings):
    has_top = any(i["scaling"] == "topper" for i in ings)
    if has_top:
        return "collins", "tall"
    if method == "built":
        return "old-fashioned", "rocks"
    return "coupe", "up"

def art(w):
    return ("an " if w[0].lower() in "aeiou" else "a ") + w

def steps_for(method, served, glass, ings):
    gl0 = glass.replace("-", " ").replace("nick and nora", "Nick & Nora")
    if glass == "old-fashioned":
        gl0 = "double old-fashioned glass" if served == "crushed-ice" else "rocks glass"
    gl = gl0
    names = " ".join(i["name"].lower() for i in ings)
    if "sugar cube" in names:
        return ["Muddle the sugar cube with the bitters and soda in a rocks glass.",
                "Add the spirits and a large ice cube, and stir briefly."] if "rinse" not in [i["scaling"] for i in ings] else \
               ["Rinse a rocks glass with absinthe and discard the excess.",
                "Muddle the sugar cube with the bitters and soda in the glass.",
                "Add the spirits and a large ice cube, and stir briefly."]
    has_top = [i["name"].lower() for i in ings if i["scaling"] == "topper"]
    rinse = [i["name"].lower() for i in ings if i["scaling"] == "rinse"]
    out = []
    if rinse:
        out.append(f"Rinse the glass with {rinse[0]} and discard the excess.")
    muddle = [i["name"].lower() for i in ings if i["scaling"] == "fixed" and re.search(r"leaves|leaf|slices|grapes|wedges|cucumber|mint|basil|tomato|sage|dill|wheel", i["name"], re.I)]
    if muddle:
        out.append(f"Gently muddle the {', '.join(muddle)} in the shaker." if method == "shaken" else f"Gently muddle the {', '.join(muddle)}.")
    egg = any("egg white" in i["name"].lower() for i in ings)
    body = [i for i in ings if i["scaling"] != "topper" and i["scaling"] != "rinse"]
    if method == "shaken":
        if egg:
            out.append("Dry shake without ice, then shake hard with ice.")
        else:
            out.append("Shake hard with ice.")
        if served == "up":
            out.append(f"Fine strain into a chilled {gl}.")
        elif served == "crushed-ice":
            out.append(f"Pour into {art(gl)} and fill with crushed ice.")
        else:
            out.append(f"Strain into {art(gl)} over fresh ice.")
    elif method == "stirred":
        out.append("Stir with ice until well chilled.")
        out.append(f"Strain into a chilled {gl}." if served == "up" else f"Strain into a {gl} over fresh ice.")
    elif method == "built":
        out.append(f"Build in {art(gl)} over ice.")
    elif method == "swizzled":
        out.append(f"Add to a {gl} with crushed ice and swizzle until the glass frosts.")
    elif method == "blended":
        out.append("Flash blend with crushed ice for a few seconds.")
        out.append(f"Pour unstrained into a {gl}.")
    if has_top:
        out.append(f"Top with {has_top[0]}.")
    return out

# ------------------------------------------------------------- record build

def build(name, ings, *, method, served, glass, garnish, site, credit, tags, personal, tab, row,
          review_notes, steps=None, ckey=None):
    ings = [tidy(dict(i)) for i in ings]
    for i in ings:
        if i.pop("_unparsed", False):
            review_notes.append(f"Couldn't read amount for '{i['name']}'.")
    spec = sum(i.get("ml", 0) for i in ings if i["scaling"] == "linear")
    spec = round(spec * 2) / 2
    rec = {
        "name": name,
        "compare_key": ckey or compare_key(name),
        "method": method,
        "served": served,
        "glass": glass,
        "designed_for": {"glass": glass, "spec_volume_ml": int(spec) if spec == int(spec) else spec},
        "ingredients": ings,
    }
    if garnish:
        rec["garnish"] = garnish
    rec["steps"] = steps or steps_for(method, served, glass, ings)
    rec["source"] = {"site": site or "House (Booze sheet)", "retrieved": RETRIEVED, "sponsored": False}
    if credit:
        rec["credit"] = credit
    if tags:
        rec["tags"] = tags
    p = {k: v for k, v in personal.items() if v}
    if p:
        rec["personal"] = p
    rec["imported_from"] = {"sheet": "Booze", "tab": tab, "row": row}
    if review_notes:
        rec["needs_review"] = True
        rec["review_notes"] = review_notes
    return rec

def s(v):
    return str(v).strip() if v not in (None, "") else None

def convert_ctt(ws, skipped):
    out = []
    for r in range(2, ws.max_row + 1):
        name, base, spec, garn, uniq, notes, thoughts, tagline, src, approved = [ws.cell(r, c).value for c in range(1, 11)]
        name = s(name)
        if not name:
            continue
        if not spec or str(spec).startswith("http"):
            skipped.append(("Cocktails to Try", r, name, "link only: " + str(spec) if spec else "no recipe"))
            continue
        ov = CTT_OVERRIDES.get(r, {})
        review = []
        ings = ov.get("ings") or parse_spec(str(spec))
        if "replace" in ov:
            ings = [ov["replace"].get(i["name"], i) for i in ings]
        if "drop" in ov:
            ings = [i for i in ings if not any(i["name"].startswith(d) for d in ov["drop"])]
        if ov.get("review"):
            review.append(ov["review"])
        garnish, glass_txt = split_garnish(garn)
        garnish = ov.get("garnish", garnish)
        method = ov.get("method") or infer_method(ings, str(spec))
        g = find_glass(glass_txt)
        if g:
            glass, served = g
        else:
            glass, served = default_glass(method, ings)
            review.append(f"Glass not in the sheet; assumed {glass}.")
        site, credit = map_source(src)
        tags = sorted({slugify(t) for t in re.split(r",", str(base or "")) if t.strip() and slugify(t) != "na"})
        if s(base) == "NA":
            tags.append("non-alcoholic")
        personal = {"notes": s(notes), "thoughts": s(thoughts), "tagline": s(tagline), "highlights": s(uniq),
                    "gad_approved": True if s(approved) else None}
        disp = ov.get("name", name)
        out.append(build(disp, ings, method=method, served=served, glass=glass, garnish=garnish and garnish.strip(),
                         site=site, credit=credit, tags=tags, personal=personal, tab="Cocktails to Try", row=r,
                         review_notes=review, steps=ov.get("steps_full"),
                         ckey=ov.get("compare_key") or (slugify(disp) if disp.startswith("Untitled") else None))
                   | ({"_extra_steps": ov["steps"]} if "steps" in ov else {}))
    return out

# ------------------------------------------------------------------ Tiki tab

TIKI_COLS = {
    "Light Rum": "Light rum", "Gold Rum": "Gold rum", "Dark Rum": "Dark rum", "Jamaican Rum": "Jamaican rum",
    "Rhum Agricole": "Rhum agricole", "Overproof Demerara Rum": "Overproof Demerara rum", "Demerara Rum": "Demerara rum",
    "Absinthe": "Absinthe", "Gin": "Gin", "Brandy": "Brandy", "Pineapple": "Pineapple juice", "Lemon": "Lemon juice",
    "Lime": "Lime juice", "OJ": "Orange juice", "Grapefruit": "Grapefruit juice", "Passionfruit": "Passionfruit",
    "Simple/Cane": "Simple syrup", "Demerara Syrup": "Demerara syrup", "Vanilla Syrup": "Vanilla syrup",
    "Cinnamon Syrup": "Cinnamon syrup", "Honey Syrup": "Honey syrup", "Orgeat": "Orgeat", "Falernum": "Falernum",
    "Grenadine": "Grenadine", "Creme de Cacao": "Crème de cacao", "Chartreuse": "Chartreuse",
    "Angostura": "Angostura bitters", "Allspice Dram": "Allspice dram", "Sweet Vermouth": "Sweet vermouth",
    "Creme de Mure": "Crème de mûre", "Banana Liquer": "Banana liqueur", "Coffee Liqueur": "Coffee liqueur",
    "Orange Liqueur": "Orange liqueur", "Coconut": "Coconut",
}

# Ingredient-cell comments that rename or split the ingredient (others become a note).
CELL_FIX = {
    "I2": [V("Overproof white Jamaican rum", 2) | {"note": "Rum Fire"},
           V("Overproof dark Jamaican rum", 1) | {"note": "Hampden Estate overproof"}],
    "O3": [V("Cognac", 0.75)],
    "J10": [V("Cachaça", 2) | {"note": "try rhum agricole blanc; alt: 1 oz tequila + 1 oz cachaça"}],
    "AM21": [V("Coconut milk", 0.5)],
    "AH30": [V("Lillet Rouge", 1.5)],
    "AL32": [V("Curaçao", 0.25)],
    "AC36": [F("Maraschino cherry syrup", "1 tsp")],
    "V45": [F("Cane syrup", "splash")],
    "R41": [V("Lime cordial", 0.5) | {"note": "Berry recommends Rose's; homemade works too"}],
    "I46": [V("Jamaican rum", 1) | {"note": "Appleton"}, V("High-ester Jamaican rum", 0.5) | {"note": "Hamilton or Doctor Bird"}],
    "AM47": [V("Coconut milk", 1)],
    "AL50": [V("Cointreau", 0.25)],
    "AM50": [V("Cream of coconut", 0.5)],
    "AM26": [V("Coconut cream", 1)],
    "AB18": [V("Falernum", 0.125)],
    "Y24": [V("Cinnamon syrup", 0.25)],
    "I49": [V("Overproof Jamaican rum", 1/3) | {"note": "Smith & Cross"}],
}
DATE_CELLS = {"AB18": "1/8", "Y24": "1/4", "I49": "1/3"}

# Extra ingredients / method notes kept in comments on the Method column.
TIKI_EXTRA = {
    2: dict(add=[V("White grapefruit juice", 1), V("Guava", 0.75), F("Ancho Reyes Verde", "1 barspoon")]),
    3: dict(step="Shake with crushed ice."),
    4: dict(add=[F("Egg white", "1 egg white")], step="Blend with 8 oz crushed ice."),
    5: dict(step="Shake with 12 oz of crushed ice and cubes."),
    12: dict(add=[V("Sherry", 0.5) | {"note": "float"}]),
    14: dict(add=[V("Campari", 0.75)]),
    18: dict(add=[V("Mango juice", 0.5)]),
    20: dict(add=[F("Mint", "2 oz, tightly packed"), V("Peach liqueur", 0.5)], step="Blend with 6 oz crushed ice."),
    23: dict(add=[V("Soda water", 0.75)]),
    26: dict(step="Double strain over ice in the mug."),
    29: dict(add=[V("Apricot liqueur", 0.5), V("Cherry liqueur", 0.5), T("Soda water")]),
    30: dict(step="Shake with crushed ice."),
    33: dict(add=[V("Berry shrub", 0.25), V("Bénédictine", 0.5), V("Crème de violette", 0.25)]),
    36: dict(step="Blend with 3 oz ice (it's a smaller drink)."),
    39: dict(add=[V("Cherry liqueur", 0.5), V("Bénédictine", 0.25), D("Orange bitters", 1), T("Soda water", 2)]),
    41: dict(add=[T("Ginger beer", 4)]),
    42: dict(add=[V("Fernet-Branca", 0.5)]),
    47: dict(add=[V("Apricot liqueur", 1)]),
    45: dict(glass=("old-fashioned", "rocks"), steps=["Squeeze the lime coin into a small rocks glass and drop it in.",
              "Add the cane syrup and rhum agricole, and swizzle briefly. Ice is optional."]),
    49: dict(add=[V("Licor 43", 4/3), V("Espresso", 2/3)]),
}

TIKI_METHOD = {"shake": "shaken", "whip shake": "shaken", "flash blend": "blended", "blender": "blended",
               "swizzle": "swizzled", "muddle": "built"}

TIKI_NAMES = {"Nui Nui/Pupule": "Nui Nui"}

def tiki_cell(header, val, coord, comment):
    """Return a list of ingredients for one Tiki ingredient cell."""
    if coord in CELL_FIX:
        out = [dict(i) for i in CELL_FIX[coord]]
    else:
        name = TIKI_COLS[header]
        v = str(val).strip()
        out = None
        m = re.fullmatch(rf"({NUM})\s*\((\w+)\)", v)
        if isinstance(val, (int, float)):
            out = [V(name, float(val))]
        elif m:
            q, kind = num(m.group(1)), m.group(2)
            if kind.lower() == "syrup":
                out = [V(f"{name} syrup", q)]
            elif kind.lower() == "diced":
                out = [V(f"{name.replace(' juice', '')} (diced)", q)]
            else:
                out = [V(f"{name} ({kind.lower()})", q)]
        elif re.fullmatch(rf"({NUM})\s*-\s*(\w+)", v):
            q, kind = re.fullmatch(rf"({NUM})\s*-\s*(\w+)", v).groups()
            out = [V(f"{kind.capitalize()} {name[0].lower() + name[1:]}" if name != "Chartreuse" else f"{kind.capitalize()} Chartreuse", num(q))]
        elif re.fullmatch(rf"({NUM})\s*tsp", v, re.I):
            q = re.match(NUM, v).group(0)
            out = [V(name, num(q) * TSP_ML / OZ_ML) | {"amount": f"{q} tsp"}]
        elif re.fullmatch(r"(\d+)\s*dash(es)?", v, re.I):
            out = [D(name, int(re.match(r"\d+", v).group(0)))]
        elif v.lower() == "barspoon":
            out = [V(name, TSP_ML / OZ_ML) | {"amount": "1 barspoon"}]
        elif v.lower() == "coin":
            out = [F("Lime", "1 coin (thin round of peel and flesh)")]
        elif v.lower() == "splash":
            out = [F(name, "splash")]
        else:
            out = [F(name, v) | {"_unparsed": True}]
        if comment and coord not in CELL_FIX:
            note = re.sub(r"\s+", " ", comment).strip()
            if out and "note" not in out[0]:
                out[0]["note"] = note
    return out

def convert_tiki(ws, skipped):
    headers = {c: ws.cell(1, c).value for c in range(1, ws.max_column + 1)}
    out = []
    for r in range(2, ws.max_row + 1):
        name = s(ws.cell(r, 1).value)
        if not name:
            continue
        ings, review = [], []
        for c in range(6, ws.max_column + 1):
            cell = ws.cell(r, c)
            if cell.value in (None, "") or headers.get(c) not in TIKI_COLS:
                continue
            comment = None
            if cell.comment:
                comment = cell.comment.text
                if "Comment:" in comment:
                    comment = comment.split("Comment:", 1)[1]
            ings += tiki_cell(headers[c], cell.value, cell.coordinate, comment)
            if cell.coordinate in DATE_CELLS:
                review.append(f"{headers[c]} amount was stored as a date in the sheet; read as {DATE_CELLS[cell.coordinate]} oz.")
        src = s(ws.cell(r, 4).value)
        if not ings:
            skipped.append(("Tiki!", r, name, ("link only: " + src) if src and src.startswith("http") and "subtletiki.com/" != src[-15:] else "no recipe"))
            continue
        extra = TIKI_EXTRA.get(r, {})
        ings += extra.get("add", [])
        # put spirits first (sheet order already is), toppers last
        ings = [i for i in ings if i["scaling"] != "topper"] + [i for i in ings if i["scaling"] == "topper"]
        mtxt = (s(ws.cell(r, 3).value) or "").lower()
        method = TIKI_METHOD.get(mtxt)
        if not method:
            method = "shaken"
            review.append("Method not in the sheet; assumed shaken.")
        garnish, glass_txt = split_garnish(ws.cell(r, 5).value)
        if garnish and garnish.lower().startswith("no garnish"):
            garnish = None
        if garnish == "?":
            garnish = None
        g = find_glass(glass_txt) or extra.get("glass")
        if g:
            glass, served = g
        else:
            glass, served = "tiki-mug", "crushed-ice"
            review.append("Glass not in the sheet; assumed tiki mug.")
        if method in ("blended", "swizzled") and served == "tall":
            served = "crushed-ice"
        site, credit = map_source(src)
        disp = TIKI_NAMES.get(name, name)
        steps = extra.get("steps") or steps_for(method, served, glass, ings)
        if extra.get("step"):
            steps = [extra["step"]] + [x for x in steps if not x.startswith(("Shake hard", "Flash blend"))]
        rec = build(disp, ings, method=method, served=served, glass=glass, garnish=garnish, site=site,
                    credit=credit, tags=["tiki"], personal={"notes": s(ws.cell(r, 2).value)}, tab="Tiki!", row=r,
                    review_notes=review, steps=steps,
                    ckey=compare_key(name) if not disp.startswith("Untitled") else None)
        if disp.startswith("Untitled"):
            rec["name"] = f"Untitled ({site})"
            rec["compare_key"] = slugify(rec["name"])
            rec.setdefault("review_notes", []).append("Unnamed in the sheet.")
            rec["needs_review"] = True
        out.append(rec)
    return out

# --------------------------------------------------------------------- main

class Dumper(yaml.SafeDumper):
    pass

def _flow_ing(dumper, data):
    return dumper.represent_mapping("tag:yaml.org,2002:map", data, flow_style=False)

# ------------------------------------------------- Mai Tai + Margaritas tabs

UNI = {"½": " 1/2", "¼": " 1/4", "¾": " 3/4", "⅓": " 1/3", "⅔": " 2/3", "⅜": " 3/8", "⅝": " 5/8", "⅛": " 1/8", "\u2044": "/"}

def clean_line(t):
    for k, v in UNI.items():
        t = t.replace(k, v)
    t = re.sub(r"\s*/\s*\d+\s*½?\s*ml\b", "", t)          # "2 oz / 60 ml"
    t = re.sub(r"\s*/\s*\d+(?:\.\d+)?\s*ml\b", "", t)
    t = re.sub(r"\s*\(\d+(?:\.\d+)?(?:ml)?\)", "", t)      # "(30ml)", "(7.5)"
    t = re.sub(r"(\d)\s*oz\b", r"\1 oz", t)
    t = re.sub(r"\bounces?\b", "oz", t)
    return re.sub(r"\s+", " ", t).strip()

MAITAI_BLOCKS = {
    # sheet title -> (display name, compare_key, site, credit)
    "Garrett Richards": ("Mai Tai", "mai-tai", "Garrett Richards", None),
    "Ultimate Mai Tai by Kevin Crossman": ("Ultimate Mai Tai", "mai-tai", "Kevin Crossman", None),
    "Maui Tai": ("Maui Tai", "maui-tai", None, None),
    "Royal Hawaiian 1971": ("Royal Hawaiian Mai Tai (1971)", "mai-tai", None, "Royal Hawaiian Hotel, Waikiki, 1971"),
    "1956 Mai Tai by Trader Vic Bergeron": ("Mai Tai (1956)", "mai-tai", None, "Trader Vic Bergeron"),
    "Simplified 1944 Mai Tai Recipe": ("Mai Tai (1944, simplified)", "mai-tai", None, "After Trader Vic, 1944"),
    "House without a Key Mai Tai, Halekulani Hotel in Waikiki": ("House Without a Key Mai Tai", "mai-tai", None, "House Without a Key, Halekulani Hotel, Waikiki"),
    "Tasting History": ("Mai Tai", "mai-tai", "Tasting History", None),
    "Island Mai Tai by Michael Thanos": ("Island Mai Tai", "island-mai-tai", "Michael Thanos", None),
    "Golden Island Mai Tai by Jason Alexander": ("Golden Island Mai Tai", "golden-island-mai-tai", "Jason Alexander", None),
    "Chuck’s Original Steak House, Waikiki, Courtesy of Les Hong": ("Chuck's Steak House Mai Tai", "mai-tai", None, "Chuck's Original Steak House, Waikiki (courtesy of Les Hong)"),
    "Tia Mia by Ivy Mix (via Lani Kai, New York City, circa 2010)": ("Tia Mia", "tia-mia", "Ivy Mix", "Lani Kai, New York City, c. 2010"),
    "Internatonal Bartenders Association (IBA)": ("Mai Tai", "mai-tai", "International Bartenders Association (IBA)", None),
    "Molasses Mai Tai by Kevin Crossman": ("Molasses Mai Tai", "molasses-mai-tai", "Kevin Crossman", None),
    "Mai Tai Planter’s Punch by Jason Alexander at Devil’s Reef, Tacoma WA": ("Mai Tai Planter's Punch", "mai-tai-planters-punch", "Jason Alexander", "Devil's Reef, Tacoma, WA"),
    "Banana Mai Tai by Kevin Crossman": ("Banana Mai Tai", "banana-mai-tai", "Kevin Crossman", None),
    "Mai Tai by Shannon Mustipher, Tiki: Modern Tropical Cockails": ("Mai Tai", "mai-tai", "Shannon Mustipher, Tiki: Modern Tropical Cocktails", None),
    "Mai Tai Swizzle by Don the Beachcomber": ("Mai Tai Swizzle", "mai-tai-swizzle", None, "Don the Beachcomber"),
    "The Reverend’s Tai by Matt Pietrek (Cocktail Wonk)": ("The Reverend's Tai", "reverends-tai", "Cocktail Wonk (Matt Pietrek)", None),
    "Trader Vic's Havana Mai Tai": ("Havana Mai Tai", "mai-tai", None, "Trader Vic"),
}

# Lines the generic parser can't handle, keyed by (block title, exact line).
ULTIMATE_BLEND = "equal parts Appleton 12, Smith & Cross, Plantation OFTD and Plantation Xaymaca"
MAITAI_LINE_FIX = {
    "Spent Lime Wedge for Shaking": [F("Lime wedge", "1 spent wedge, shaken with the drink")],
    "1 oz Pineapple Juice / Mango Puree / Guava Puree / Passionfruit Puree":
        [V("Pineapple juice", 1) | {"note": "or mango, guava or passionfruit purée"}],
    " 3/4 oz Mai Tai Concentrate":
        [V("Orgeat", 0.75 * 7 / 19) | {"note": "from 3/4 oz Mai Tai concentrate (7 orgeat : 12 curaçao)"},
         V("Orange curaçao", 0.75 * 12 / 19) | {"note": "from 3/4 oz Mai Tai concentrate"}],
    "1 to 1- 1/2 oz Light Rum": [V("Light rum", 1.25) | {"note": "1 to 1 1/2 oz"}],
    "Float 1/2 oz Lemon Hart 151 Rum": [V("Lemon Hart 151 rum", 0.5) | {"note": "float"}],
    "2 oz Ultimate Mai Tai Rum Blend": [V("Ultimate Mai Tai rum blend", 2) | {"note": ULTIMATE_BLEND}],
    "1 oz Gold or Amber Rum": [V("Gold or amber rum", 1)],
    "1 1/2 oz Gold or Amber Rum": [V("Gold or amber rum", 1.5)],
    "1 1/2 oz Sweet and Sour mix": [V("Sweet and sour mix", 1.5)],
    "1 oz Dark Rum or Demerara Dark Rum (Float)": [V("Dark rum or dark Demerara rum", 1) | {"note": "float"}],
    "1/2 oz Falernum or Orgeat syrup": [V("Falernum or orgeat", 0.5)],
    "1 dash Falernum": [D("Falernum", 1)],
    "1 dash Grenadine": [D("Grenadine", 1)],
    "1 oz lime juice 1 oz Mai Tai Mix (3/8 oz orgeat + 5/8 oz orange Curacao ) 1 oz aged Jamaican Rum 1 oz aged Rhum St. James":
        [V("Lime juice", 1), V("Orgeat", 0.375) | {"note": "from 1 oz Mai Tai mix"},
         V("Orange curaçao", 0.625) | {"note": "from 1 oz Mai Tai mix"},
         V("Aged Jamaican rum", 1), V("Rhum St. James", 1) | {"note": "aged"}],
    "1 oz Jamaican": [V("Jamaican rum", 1)],
    "¼ oz / 7½ ml Rock Candy/Rich Simple Syrup or Demerara Syrup": [V("Rock candy syrup", 0.25) | {"note": "or rich simple or demerara syrup"}],
    "1 oz white rum agricole": [V("Rhum agricole blanc", 1)],
}
MAITAI_EXTRA = {
    "Golden Island Mai Tai by Jason Alexander": dict(method="blended"),
    "Tia Mia by Ivy Mix (via Lani Kai, New York City, circa 2010)": dict(garnish="Mint, lime wheel"),
    "Mai Tai Swizzle by Don the Beachcomber": dict(garnish="4 mint sprigs"),
}
NOTE_CELLS = {"A15"}  # "Too sweet?" sits in the name column under Royal Hawaiian 1971

def read_blocks(ws, name_col, body_col):
    blocks, cur = [], None
    for r in range(1, ws.max_row + 1):
        nm = ws.cell(r, name_col).value
        body = ws.cell(r, body_col).value
        coord = ws.cell(r, name_col).coordinate
        if nm and str(nm).strip() in MAITAI_BLOCKS:
            cur = {"title": str(nm).strip(), "row": r, "lines": [], "notes": []}
            blocks.append(cur)
        elif nm and coord in NOTE_CELLS and cur:
            cur["notes"].append(str(nm).strip())
        if cur and body:
            cur["lines"].append(str(body))
            side = ws.cell(r, body_col + 1).value
            if side and cur["lines"][-1].strip().startswith(("¾ oz Mai Tai", " 3/4 oz Mai")):
                pass
    return blocks

def convert_maitai(ws, skipped):
    blocks = read_blocks(ws, 1, 2) + read_blocks(ws, 4, 5)
    out = []
    for b in blocks:
        disp, ckey, site, credit = MAITAI_BLOCKS[b["title"]]
        ings, steps, garnish, sub, review = [], [], None, None, []
        for raw in b["lines"]:
            line = clean_line(raw)
            if sub is not None:                     # sub-recipe (e.g. molasses syrup)
                sub["lines"].append(line)
                continue
            if line.endswith(":"):
                sub = {"name": line[:-1], "lines": []}
                continue
            if line.lower().startswith("garnish"):
                garnish = re.sub(r"^garnish( with)?\s*", "", line, flags=re.I)
                garnish = re.sub(r"\s+(?=Pineapple)", ", ", garnish)
                garnish = garnish[0].upper() + garnish[1:]
                continue
            if re.match(r"^(shake|zip|combine|stir)\b", line, re.I):
                steps.append(line)
                continue
            sq = lambda x: re.sub(r"\s+", "", clean_line(x))
            key = next((k for k in MAITAI_LINE_FIX if sq(k) == sq(line)), None)
            if key:
                ings += [dict(i) for i in MAITAI_LINE_FIX[key]]
            else:
                ings += [i for i in parse_spec(line.replace(",", " "))]
        if sub:
            for i in ings:
                if i["name"].lower().startswith(sub["name"].lower()):
                    i["note"] = "1 cup hot water, 2 cups sugar, 2 tbsp mild molasses; stir to dissolve"
        extra = MAITAI_EXTRA.get(b["title"], {})
        garnish = extra.get("garnish", garnish)
        method = extra.get("method", "shaken")
        glass, served = ("tiki-mug", "crushed-ice") if method == "blended" else ("old-fashioned", "crushed-ice")
        review.append(f"Glass not in the sheet; assumed {glass.replace('-', ' ')} with crushed ice.")
        if steps and method == "blended":
            steps = ["Flash blend with crushed ice.", "Pour unstrained into a tiki mug."]
        elif steps:
            steps = [re.sub(r"\s*(and garnish with|Garnish with).*$", "", x).strip() for x in steps]
            steps = [x if x.endswith(".") else x + "." for x in steps]
            steps = [x.replace("Shake with ice.", "Shake with ice.") for x in steps]
            steps += ["Pour into a double old-fashioned glass and top with crushed ice."] if "crushed" not in " ".join(steps) else ["Pour unstrained into a double old-fashioned glass."]
        rec = build(disp, ings, method=method, served=served, glass=glass, garnish=garnish, site=site,
                    credit=credit, tags=["tiki", "mai-tai"], personal={"notes": "; ".join(b["notes"]) or None},
                    tab="Mai Tai", row=b["row"], review_notes=review, steps=steps or None, ckey=ckey)
        rec["_slug_hint"] = slugify(disp) + ("-" + source_slug(site) if disp == "Mai Tai" else "")
        if ckey != "mai-tai":
            rec["related"] = ["mai-tai"]
            rec = {k: rec[k] for k in list(rec) if k not in ("imported_from", "needs_review", "review_notes")} | \
                  {k: rec[k] for k in ("imported_from", "needs_review", "review_notes") if k in rec}
        out.append(rec)
    return out

MARG_BLOCKS = {
    "Difford's Margarita on the Rocks": ("Margarita on the Rocks", "margarita", "Difford's Guide", ("old-fashioned", "rocks")),
    "Difford's Improved Trashy Margarita": ("Improved Trashy Margarita", "trashy-margarita", "Difford's Guide", None),
    "Riff": ("Margarita (house riff)", "margarita", None, None),
}
MARG_NAME = {"reposado (Tres Agaves)": ("Reposado tequila", "Tres Agaves"), "triple sec (De Kuypers)": ("Triple sec", "De Kuyper"),
             "Lime": ("Lime juice", None), "Agave syrup": ("Agave syrup", None),
             "Patrón Reposado tequila": ("Reposado tequila", "Patrón"), "Patrón Silver blanco tequila": ("Blanco tequila", "Patrón Silver"),
             "Cointreau triple sec liqueur": ("Cointreau", None), "Lime juice (freshly squeezed)": ("Lime juice", None),
             "Lemon juice (freshly squeezed)": ("Lemon juice", None),
             "Monin Pure Cane Syrup (65.0°brix, equivalent to 2:1 rich syrup)": ("Rich cane syrup (2:1)", "Monin Pure Cane, 65° Brix"),
             "Chilled water": ("Chilled water", None)}

def convert_margaritas(ws, skipped):
    out, cur = [], None
    rows = []
    for r in range(1, ws.max_row + 1):
        b, c, d = (ws.cell(r, i).value for i in (2, 3, 4))
        if b and str(b).strip() in MARG_BLOCKS:
            cur = {"title": str(b).strip(), "row": r, "items": []}
            rows.append(cur)
        if cur and d not in (None, ""):
            cur["items"].append((c, str(d).strip()))
    for blk in rows:
        disp, ckey, site, glass = MARG_BLOCKS[blk["title"]]
        ings, review = [], []
        for qty, name in blk["items"]:
            q = clean_line(str(qty)) if isinstance(qty, str) else str(qty)
            if name.startswith("Saline solution"):
                ings.append(ing_dash("Saline solution (20%)", int(q.split()[0]), "drop") | {"note": "optional"})
                continue
            if name.startswith("Difford's Margarita Bitters"):
                ings.append(ing_dash("Difford's Margarita Bitters", int(q.split()[0]), "drop")
                            | ({"note": "optional"} if "optional" in name else {}))
                continue
            if name.startswith("Egg white"):
                ings.append(F("Egg white", q) | {"note": "pasteurised; or 3 dashes Fee Foam, aquafaba or a vegan replacement"})
                continue
            qn = num(re.sub(r"\s*oz$", "", q))
            nm, note = MARG_NAME.get(name, (name, None))
            ing = V(nm, qn)
            if note:
                ing["note"] = note
            ings.append(ing)
        method = "shaken"
        if glass:
            g, served = glass
        else:
            g, served = "coupe", "up"
            review.append("Glass not in the sheet; assumed coupe.")
        rec = build(disp, ings, method=method, served=served, glass=g, garnish=None, site=site, credit=None,
                    tags=["tequila", "margarita"], personal={}, tab="Margaritas", row=blk["row"], review_notes=review,
                    ckey=ckey)
        if ckey != "margarita":
            rec["related"] = ["margarita"]
        out.append(rec)
    return out

def main(xlsx, outdir):
    import os
    wb = openpyxl.load_workbook(xlsx)
    skipped = []
    recs = (convert_ctt(wb["Cocktails to Try"], skipped) + convert_tiki(wb["Tiki!"], skipped)
            + convert_maitai(wb["Mai Tai"], skipped) + convert_margaritas(wb["Margaritas"], skipped))
    used = set()
    for rec in recs:
        extra = rec.pop("_extra_steps", None)
        if extra:
            rec["steps"] = extra + rec["steps"]
        hint = rec.pop("_slug_hint", None)
        slug = hint if hint else rec["compare_key"] if rec["name"].startswith("Untitled") else f"{rec['compare_key']}-{source_slug(rec['source']['site'] if not rec['source']['site'].startswith('House') else None)}"
        base, n = slug, 2
        while slug in used:
            slug = f"{base}-{n}"; n += 1
        used.add(slug)
        rec["_slug"] = slug
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from drinks_io import merge
    from_sheet = lambda v: (v.get("imported_from") or {}).get("sheet") == "Booze"
    written = merge(recs, outdir, drop=from_sheet)
    print(f"{len(written)} drink files written to {outdir}")
    json.dump({"written": len(recs), "skipped": skipped,
               "review": [(r["name"], r.get("review_notes")) for r in recs if r.get("needs_review")]},
              open("booze-import-report.json", "w"), indent=1, ensure_ascii=False)
    print(len(recs), "recipes imported;", len(skipped), "rows skipped;",
          sum(1 for r in recs if r.get("needs_review")), "need review (see booze-import-report.json)")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
