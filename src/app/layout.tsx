import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Off-Spec", template: "%s · Off-Spec" },
  description: "A cocktail repository for comparing recipes for the same drink.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <header className="border-b border-neutral-200">
          <nav className="mx-auto flex max-w-4xl items-center gap-6 px-6 py-4">
            <Link href="/" className="text-lg font-semibold tracking-tight">
              Off-Spec
            </Link>
            <Link href="/recipes" className="text-sm text-neutral-600 hover:text-foreground">
              Recipes
            </Link>
            <Link href="/compare" className="text-sm text-neutral-600 hover:text-foreground">
              Compare
            </Link>
          </nav>
        </header>
        <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-10">{children}</main>
      </body>
    </html>
  );
}
