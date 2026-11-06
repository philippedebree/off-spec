import fs from "node:fs";
import path from "node:path";
import { load as parseYaml } from "js-yaml";
import type { Recipe } from "./types";

const RECIPES_DIR = path.join(process.cwd(), "content", "recipes");

let cache: Recipe[] | null = null;

/** Load every *.yaml / *.yml recipe at build time. */
export function getAllRecipes(): Recipe[] {
  if (cache) return cache;
  if (!fs.existsSync(RECIPES_DIR)) return (cache = []);

  cache = fs
    .readdirSync(RECIPES_DIR)
    .filter((f) => /\.ya?ml$/.test(f))
    .map((file) => {
      const raw = parseYaml(fs.readFileSync(path.join(RECIPES_DIR, file), "utf8")) as Omit<Recipe, "slug">;
      return { ...raw, slug: file.replace(/\.ya?ml$/, "") };
    })
    .sort((a, b) => a.name.localeCompare(b.name));
  return cache;
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
