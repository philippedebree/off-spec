import Link from "next/link";
import { getAllRecipes, getCompareGroups } from "@/lib/recipes";

export default function Home() {
  const recipes = getAllRecipes();
  const multi = [...getCompareGroups()].filter(([, v]) => v.length > 1);

  return (
    <div className="space-y-10">
      <section className="space-y-3">
        <h1 className="text-4xl font-semibold tracking-tight">Every version of the drink, side by side.</h1>
        <p className="text-neutral-600">
          {recipes.length} recipes, {multi.length} drinks with more than one version to compare.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Compare</h2>
        <ul className="flex flex-wrap gap-2">
          {multi.map(([key, versions]) => (
            <li key={key}>
              <Link href={`/compare/${key}`} className="rounded-full border border-neutral-300 px-3 py-1 text-sm hover:bg-neutral-100">
                {versions[0].name} · {versions.length} versions
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
