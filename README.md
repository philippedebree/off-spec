# off-spec
A cocktail repository website, focusing on comparison of specs and easy of cocktail discovery

Built with Next.js (App Router), TypeScript and Tailwind CSS. Recipes are YAML files in `content/recipes/` (the scraper's output). They're read at build time, and every page is pre-rendered as static HTML.

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
content/recipes/        YAML recipes, one per recipe per source (3 samples to replace)
src/lib/types.ts        TypeScript types that mirror the scraper schema
src/lib/recipes.ts      Loads YAML and groups recipes by compare_key
src/lib/scale.ts        Glass-size scaler (fill level, dilution, non-linear ingredients)
src/components/GlassScaler.tsx   Client-side glass picker that rescales the spec live
src/app/recipes/        Recipe list and recipe detail pages
src/app/compare/        Compare index and side-by-side table per drink
```

## Adding recipes

Copy the scraper's YAML files into `content/recipes/`. Each file name becomes the URL slug. Recipes that share a `compare_key` appear together on `/compare/<key>`.

Only `steps` (our rewritten text) are rendered. `reference_steps` (source wording) are never shown.

## Scripts

- `npm run dev`: start the dev server
- `npm run build`: production build
- `npm run lint`: run ESLint
