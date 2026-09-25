"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { Eye, EyeOff, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { createClient } from "@/lib/supabase/client"
import { supabaseConfigured } from "@/lib/supabase/config"

export function SignUpForm() {
  const router = useRouter()
  const [showPassword, setShowPassword] = React.useState(false)
  const [pending, setPending] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [sent, setSent] = React.useState(false)

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setPending(true)

    const form = new FormData(event.currentTarget)
    const email = String(form.get("email") ?? "")
    const password = String(form.get("password") ?? "")

    try {
      const { data, error } = await createClient().auth.signUp({ email, password })
      if (error) {
        setError(error.message)
        return
      }
      // A session on the response means email confirmation is off and this account is
      // already active - otherwise Supabase is waiting on a confirmation link, and there
      // is nothing to sign in to yet.
      if (data.session) {
        router.replace("/dashboard")
        router.refresh()
      } else {
        setSent(true)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reach the sign-up service.")
    } finally {
      setPending(false)
    }
  }

  if (!supabaseConfigured) {
    return (
      <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
        Sign-up is not configured: <code>NEXT_PUBLIC_SUPABASE_URL</code> and{" "}
        <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code> are missing from this build. On Vercel
        they are inlined at build time, so add them and redeploy.
      </p>
    )
  }

  if (sent) {
    return (
      <p className="rounded-lg border border-border/60 bg-muted/30 p-4 text-sm text-muted-foreground">
        Check your email to confirm your account, then sign in.
      </p>
    )
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="you@company.com"
          required
          className="h-10"
        />
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor="password">Password</Label>
        <div className="relative">
          <Input
            id="password"
            name="password"
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            placeholder="At least 8 characters"
            required
            minLength={8}
            className="h-10 pr-10"
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? "sign-up-error" : undefined}
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-muted-foreground hover:text-foreground"
          >
            {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            <span className="sr-only">{showPassword ? "Hide" : "Show"} password</span>
          </button>
        </div>
      </div>

      {error && (
        <p id="sign-up-error" role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      <Button
        type="submit"
        disabled={pending}
        className="h-10 bg-brand text-brand-foreground hover:bg-brand/90"
      >
        {pending && <Loader2 className="size-4 animate-spin" />}
        {pending ? "Creating account…" : "Create account"}
      </Button>
    </form>
  )
}
