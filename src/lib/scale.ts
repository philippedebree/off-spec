// Glass-size scaler — implements "Scaling recipes to glass size" from the
// project notes. Pure functions so it runs on server or client.
import type { Ingredient, Method, Recipe, Served } from "./types";

export const FILL_LEVEL = 0.85;

/** Dilution as a fraction of spec volume (rules of thumb from the notes). */
export function dilutionFor(method: Method): number {
  switch (method) {
    case "shaken":
    case "blended":
      return 0.35;
    case "stirred":
    case "thrown":
      return 0.25;
    default:
      return 0.25;
  }
}

/** Target spec volume (ml) for a glass of the given brim capacity. */
export function targetSpecMl(capacityMl: number, method: Method): number {
  return (capacityMl * FILL_LEVEL) / (1 + dilutionFor(method));
}

/** Fill-level scaling only makes sense for drinks served up. */
export function isScalable(served: Served): boolean {
  return served === "up";
}

export interface ScaledIngredient extends Ingredient {
  scaledMl?: number;
  scaledDashes?: number;
  note?: string;
}

const roundTo = (n: number, step: number) => Math.round(n / step) * step;

export function scaleRecipe(recipe: Recipe, capacityMl: number) {
  const target = targetSpecMl(capacityMl, recipe.method);
  const factor = target / recipe.designed_for.spec_volume_ml;

  const ingredients: ScaledIngredient[] = recipe.ingredients.map((ing) => {
    switch (ing.scaling) {
      case "linear": {
        if (ing.ml == null) return { ...ing };
        const exact = ing.ml * factor;
        // Metric rounds more cleanly than ¼ oz: 5 ml steps, 2.5 ml for small amounts.
        const step = exact < 15 ? 2.5 : 5;
        const scaledMl = ing.round === "down" ? Math.floor(exact / step) * step : roundTo(exact, step);
        return { ...ing, scaledMl: Math.max(scaledMl, step) };
      }
      case "dash": {
        if (ing.dashes == null) return { ...ing };
        // Scale gently: half the change, whole dashes, never below 1.
        const gentle = ing.dashes * (1 + (factor - 1) / 2);
        return { ...ing, scaledDashes: Math.max(1, Math.round(gentle)) };
      }
      case "fixed":
      case "rinse":
        return { ...ing, note: "unchanged" };
      case "topper":
        return { ...ing, note: "top to fill" };
    }
  });

  return { factor, targetMl: target, ingredients };
}

export const mlToOz = (ml: number) => Math.round((ml / 29.5735) * 100) / 100;

/** Preset glassware (brim capacities). Users can add their own later. */
export const GLASS_PRESETS = [
  { label: "4.5 oz Nick & Nora", ml: 133 },
  { label: "5 oz coupe", ml: 148 },
  { label: "6 oz coupe", ml: 177 },
  { label: "7 oz coupe / martini", ml: 207 },
  { label: "8 oz coupe / martini", ml: 237 },
];
