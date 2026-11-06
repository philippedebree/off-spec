import Link from "next/link";
import { getAllRecipes } from "@/lib/recipes";

export const metadata = { title: "Recipes" };

export default function RecipesPage() {
  const recipes = getAllRecipes();
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold">Recipes</h1>
      <ul className="divide-y divide-neutral-200">
        {recipes.map((r) => (
          <li key={r.slug} className="flex items-baseline justify-between py-3">
            <Link href={`/recipes/${r.slug}`} className="font-medium hover:underline">
              {r.name}
            </Link>
            <span className="text-sm text-neutral-500">
              {r.method} · {r.source.site}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
