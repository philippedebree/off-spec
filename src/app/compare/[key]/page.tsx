import Link from "next/link";
import { notFound } from "next/navigation";
import { getCompareGroups, getVersions } from "@/lib/recipes";

export function generateStaticParams() {
  return [...getCompareGroups().keys()].map((key) => ({ key }));
}

export async function generateMetadata({ params }: PageProps<"/compare/[key]">) {
  const { key } = await params;
  const v = getVersions(key);
  return { title: v.length ? `Compare: ${v[0].name}` : "Not found" };
}

export default async function CompareDrink({ params }: PageProps<"/compare/[key]">) {
  const { key } = await params;
  const versions = getVersions(key);
  if (!versions.length) notFound();

  // Union of ingredient names across versions, in first-seen order.
  const names = [...new Set(versions.flatMap((v) => v.ingredients.map((i) => i.name)))];

  const cell = (v: (typeof versions)[number], name: string) => {
    const ing = v.ingredients.find((i) => i.name === name);
    if (!ing) return "—";
    if (ing.ml != null) return `${ing.ml} ml`;
    return ing.amount ?? "✓";
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold">{versions[0].name}: {versions.length} versions</h1>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-neutral-300 text-left">
              <th className="py-2 pr-4 font-medium">Ingredient</th>
              {versions.map((v) => (
                <th key={v.slug} className="py-2 pr-4 font-medium">
                  <Link href={`/recipes/${v.slug}`} className="underline">
                    {v.source.site}
                  </Link>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {names.map((n) => (
              <tr key={n} className="border-b border-neutral-200">
                <td className="py-2 pr-4">{n}</td>
                {versions.map((v) => (
                  <td key={v.slug} className="py-2 pr-4">{cell(v, n)}</td>
                ))}
              </tr>
            ))}
            <tr className="text-neutral-500">
              <td className="py-2 pr-4">Spec volume</td>
              {versions.map((v) => (
                <td key={v.slug} className="py-2 pr-4">{v.designed_for.spec_volume_ml} ml</td>
              ))}
            </tr>
            <tr className="text-neutral-500">
              <td className="py-2 pr-4">Method / glass</td>
              {versions.map((v) => (
                <td key={v.slug} className="py-2 pr-4">{v.method} · {v.glass}</td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
