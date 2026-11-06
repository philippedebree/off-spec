import fs from "node:fs";
import path from "node:path";
import { load as parseYaml } from "js-yaml";
import type { Drink, Recipe } from "./types";

// One file per drink: content/drinks/<compare_key>.yaml, holding every version.
const DRINKS_DIR = path.join(process.cwd(), "content", "drinks");

let drinkCache: Drink[] | null = null;
let recipeCache: Recipe[] | null = null;

/** Load every drink file at build time. */
export function getAllDrinks(): Drink[] {
  if (drinkCache) return drinkCache;
  if (!fs.existsSync(DRINKS_DIR)) return (drinkCache = []);

  drinkCache = fs
    .readdirSync(DRINKS_DIR)
    .filter((f) => /\.ya?ml$/.test(f))
    .map((file) => {
      const raw = parseYaml(fs.readFileSync(path.join(DRINKS_DIR, file), "utf8")) as Omit<Drink, "key">;
      return { ...raw, key: file.replace(/\.ya?ml$/, "") };
    })
    .sort((a, b) => a.name.localeCompare(b.name));
  return drinkCache;
}

/** Every version of every drink, flattened into standalone recipes (one per URL). */
export function getAllRecipes(): Recipe[] {
  if (recipeCache) return recipeCache;
  recipeCache = getAllDrinks()
    .flatMap((drink) =>
      drink.versions.map(
        ({ name, ...version }): Recipe => ({
          ...version,
          name: name ?? drink.name,
          compare_key: drink.key,
          tags: drink.tags,
          related: drink.related,
        }),
      ),
    )
    .sort((a, b) => a.name.localeCompare(b.name));
  return recipeCache;
}

export function getRecipe(slug: string): Recipe | undefined {
  return getAllRecipes().find((r) => r.slug === slug);
}

/** Group versions of the same drink across sources for the comparison feature. */
export function getCompareGroups(): Map<string, Recipe[]> {
  const groups = new Map<string, Recipe[]>();
  for (const r of getAllRecipes()) {
    const list = groups.get(r.compare_key) ?? [];
    list.push(r);
    groups.set(r.compare_key, list);
  }
  return groups;
}

export function getVersions(compareKey: string): Recipe[] {
  return getCompareGroups().get(compareKey) ?? [];
}
