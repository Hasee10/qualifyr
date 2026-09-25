import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Sign in · Qualifyr",
};

/** Placeholder. Phase 2 wires this to Supabase Auth. */
export default function SignInPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Welcome back</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Sign in to your account to continue.
      </p>

      <p className="mt-8 rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
        Sign-in is being wired up to Supabase Auth.
      </p>

      <Link
        href="/"
        className="mt-8 inline-block text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        ← Back to home
      </Link>
    </div>
  );
}
