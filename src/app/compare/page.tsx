import Link from "next/link";
import { getCompareGroups } from "@/lib/recipes";

export const metadata = { title: "Compare" };

export default function ComparePage() {
  const groups = [...getCompareGroups()].sort(([a], [b]) => a.localeCompare(b));
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold">Compare</h1>
      <ul className="divide-y divide-neutral-200">
        {groups.map(([key, versions]) => (
          <li key={key} className="flex justify-between py-3">
            <Link href={`/compare/${key}`} className="font-medium hover:underline">
              {versions[0].name}
            </Link>
            <span className="text-sm text-neutral-500">
              {versions.length} version{versions.length === 1 ? "" : "s"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
