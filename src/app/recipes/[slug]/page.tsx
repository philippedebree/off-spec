import Link from "next/link";
import { notFound } from "next/navigation";
import GlassScaler from "@/components/GlassScaler";
import { getAllRecipes, getRecipe, getVersions } from "@/lib/recipes";

export function generateStaticParams() {
  return getAllRecipes().map((r) => ({ slug: r.slug }));
}

export async function generateMetadata({ params }: PageProps<"/recipes/[slug]">) {
  const { slug } = await params;
  const r = getRecipe(slug);
  return { title: r ? `${r.name} (${r.source.site})` : "Not found" };
}

export default async function RecipePage({ params }: PageProps<"/recipes/[slug]">) {
  const { slug } = await params;
  const recipe = getRecipe(slug);
  if (!recipe) notFound();

  const others = getVersions(recipe.compare_key).length - 1;

  return (
    <article className="space-y-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold">{recipe.name}</h1>
        <p className="text-sm text-neutral-500">
          {recipe.method} · served {recipe.served} · {recipe.glass}
          {recipe.needs_review && <span className="ml-2 rounded bg-amber-100 px-1.5 text-amber-800">needs review</span>}
        </p>
        {others > 0 && (
          <Link href={`/compare/${recipe.compare_key}`} className="text-sm underline">
            Compare with {others} other version{others === 1 ? "" : "s"}
          </Link>
        )}
      </header>

      <GlassScaler recipe={recipe} />

      {recipe.garnish && (
        <p>
          <span className="font-medium">Garnish:</span> {recipe.garnish}
        </p>
      )}

      {/* Only our own rewritten steps are rendered; reference_steps never are. */}
      {recipe.steps && (
        <ol className="list-decimal space-y-1 pl-5">
          {recipe.steps.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ol>
      )}

      <footer className="text-sm text-neutral-500">
        Spec via{" "}
        <a href={recipe.source.url} className="underline" rel="noopener">
          {recipe.source.site}
        </a>
        {recipe.credit && <> · {recipe.credit}</>}
        {recipe.source.sponsored && <> · sponsored content</>}
      </footer>
    </article>
  );
}
