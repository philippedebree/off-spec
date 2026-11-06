"use client";

import { useState } from "react";
import type { Recipe } from "@/lib/types";
import { GLASS_PRESETS, isScalable, mlToOz, scaleRecipe } from "@/lib/scale";

export default function GlassScaler({ recipe }: { recipe: Recipe }) {
  const original = recipe.designed_for.glass_capacity_ml;
  const [capacity, setCapacity] = useState<number | null>(null);
  const [unit, setUnit] = useState<"ml" | "oz">("ml");

  const scalable = isScalable(recipe.served);
  const scaled = scalable && capacity ? scaleRecipe(recipe, capacity) : null;

  const fmt = (ml: number) => (unit === "ml" ? `${ml} ml` : `${mlToOz(ml)} oz`);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        {scalable ? (
          <label className="flex items-center gap-2">
            Your glass
            <select
              className="rounded border border-neutral-300 bg-transparent px-2 py-1"
              value={capacity ?? ""}
              onChange={(e) => setCapacity(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">
                As written{original ? ` (${recipe.designed_for.glass}, ${original} ml)` : ""}
              </option>
              {GLASS_PRESETS.map((g) => (
                <option key={g.ml} value={g.ml}>
                  {g.label}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <p className="text-neutral-500">Served over ice — keep the spec and let the topper or ice absorb glass size.</p>
        )}
        <button
          className="rounded border border-neutral-300 px-2 py-1"
          onClick={() => setUnit(unit === "ml" ? "oz" : "ml")}
        >
          Show {unit === "ml" ? "oz" : "ml"}
        </button>
        {scaled && <span className="text-neutral-500">× {scaled.factor.toFixed(2)}</span>}
      </div>

      <ul className="divide-y divide-neutral-200">
        {recipe.ingredients.map((ing, i) => {
          const s = scaled?.ingredients[i];
          let amount = ing.amount ?? "";
          if (ing.ml != null) amount = fmt(s?.scaledMl ?? ing.ml);
          if (ing.dashes != null) {
            const d = s?.scaledDashes ?? ing.dashes;
            amount = `${d} dash${d === 1 ? "" : "es"}`;
          }
          return (
            <li key={ing.name} className="flex justify-between py-2">
              <span>{ing.name}</span>
              <span className="tabular-nums text-neutral-600">{amount}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
