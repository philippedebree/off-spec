// Mirrors the drink files in content/drinks (see project notes: "Recipe data schema").
// One file per drink; each holds every version (spec) of that drink as `versions`.
// The site flattens versions into standalone Recipe objects, one per /recipes/<slug>.

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
  /** Bottle suggestion or prep note, e.g. "Smith & Cross", "float". */
  note?: string;
}

export interface Recipe {
  slug: string; // the version's slug; its URL is /recipes/<slug>
  name: string;
  compare_key: string; // the drink file name
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
    url?: string;
    retrieved: string;
    sponsored?: boolean;
  };
  credit?: string;
  tags?: string[];
  related?: string[];
  needs_review?: boolean;
  review_notes?: string[];
  /** Private tasting notes from the Booze sheet. Never rendered on the site. */
  personal?: {
    notes?: string;
    thoughts?: string;
    tagline?: string;
    highlights?: string;
    gad_approved?: boolean;
  };
  /** Where an imported record came from (e.g. the Booze Google Sheet). */
  imported_from?: { sheet: string; tab: string; row: number };
}

/** A version as stored in a drink file: drink-level fields live on the Drink. */
export type Version = Omit<Recipe, "compare_key" | "tags" | "related" | "name"> & {
  /** Only present when the version is named differently from the drink. */
  name?: string;
};

export interface Drink {
  key: string; // derived from the file name, e.g. "mai-tai"
  name: string;
  tags?: string[];
  related?: string[];
  versions: Version[];
}
