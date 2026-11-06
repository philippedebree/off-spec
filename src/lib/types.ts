// Mirrors the YAML schema produced by the scraper (see project notes:
// "Recipe data schema"). One file per recipe per source in content/recipes.

export type Method = "shaken" | "stirred" | "built" | "blended" | "thrown" | "swizzled";
export type Served = "up" | "rocks" | "tall" | "crushed-ice";
export type ScalingClass = "linear" | "dash" | "fixed" | "rinse" | "topper";

export interface Ingredient {
  name: string;
  ml?: number;
  oz?: number;
  /** Free-text amount for non-volumetric items, e.g. "2 dashes", "1 white". */
  amount?: string;
  dashes?: number;
  scaling: ScalingClass;
  /** Strong accents (Fernet, Islay float…) round down rather than up. */
  round?: "down";
}

export interface Recipe {
  slug: string; // derived from file name
  name: string;
  compare_key: string;
  method: Method;
  served: Served;
  glass: string;
  designed_for: {
    glass: string;
    glass_capacity_ml?: number;
    spec_volume_ml: number;
  };
  ingredients: Ingredient[];
  garnish?: string;
  /** Source wording — must be rewritten before publishing. Not rendered. */
  reference_steps?: string[];
  /** Our own rewritten method text. Rendered when present. */
  steps?: string[];
  source: {
    site: string;
    url: string;
    retrieved: string;
    sponsored?: boolean;
  };
  credit?: string;
  tags?: string[];
  related?: string[];
  needs_review?: boolean;
}
