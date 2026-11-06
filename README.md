# off-spec
A cocktail repository website, focusing on comparison of specs and easy of cocktail discovery

Built with Next.js (App Router), TypeScript and Tailwind CSS. Recipes are YAML files in `content/drinks/`, one file per drink holding every version (spec) of it. They're read at build time, and every page is pre-rendered as static HTML.

## Getting started (Windows)

Requires Node.js 20.9 or newer.

```powershell
cd C:\Users\phili\Documents\off-spec
npm install
npm run dev
```

Open http://localhost:3000.

## Structure

```
content/drinks/         One YAML file per drink (e.g. mai-tai.yaml) with all its versions
scripts/                Import and merge tools (see "Adding recipes")
src/lib/types.ts        TypeScript types for drinks, versions and ingredients
src/lib/recipes.ts      Loads drink files and flattens versions into recipe pages
src/lib/scale.ts        Glass-size scaler (fill level, dilution, non-linear ingredients)
src/components/GlassScaler.tsx   Client-side glass picker that rescales the spec live
src/app/recipes/        Recipe list and recipe detail pages
src/app/compare/        Compare index and side-by-side table per drink
```

## Adding recipes

Each drink is one file, `content/drinks/<drink>.yaml`. The file name is the drink's key and its comparison page is `/compare/<drink>`. Each entry under `versions:` is one spec; its `slug` is its page URL, `/recipes/<slug>`. To add a spec by hand, add an entry to `versions:`.

- **Scraper output** (one file per recipe): `python scripts/merge-into-drinks.py path/to/scraped content/drinks`. Each recipe is added to the drink named by its `compare_key`; re-running replaces versions with the same slug.
- **Booze Google Sheet**: export it as .xlsx, then `python scripts/import-booze-sheet.py Booze.xlsx content/drinks`. Re-running replaces everything that came from the sheet and leaves other versions alone.

Both need `pip install openpyxl pyyaml`.

Only `steps` (our rewritten text) are rendered. `reference_steps` (source wording) are never shown.

## Scripts

- `npm run dev`: start the dev server
- `npm run build`: production build
- `npm run lint`: run ESLint
