import { useState, type FormEvent } from "react";
import { api, json, setToken } from "./api";
import type { User } from "./types";

export function AccountView({ onLogin }: { onLogin: (user: User) => void }) {
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const result = await api<{ user: User; token: string }>(
        `/auth/${register ? "register" : "login"}`,
        json({
          username: form.get("username"),
          password: form.get("password"),
          ...(register ? { display_name: form.get("display_name") } : {}),
        }),
      );
      setToken(result.token);
      onLogin(result.user);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-layout">
      <section className="auth-story">
        <div className="brand">
          <span className="logo animated-logo">L</span>
          <span>LitLens</span>
          <small>DESKTOP</small>
        </div>
        <div className="auth-copy">
          <span className="eyebrow">A PRIVATE RESEARCH ATELIER</span>
          <h1>
            Read with
            <br />
            clarity.
            <br />
            <em>Think with evidence.</em>
          </h1>
        </div>
      </section>
      <section className="auth-side">
        <form className="auth-card glass-card" onSubmit={submit}>
          <span className="eyebrow">LITLENS WORKSPACE</span>
          <h2>{register ? "Create your space" : "Welcome back"}</h2>
          <p className="muted">
            {register
              ? "A quiet place for serious research."
              : "Sign in to continue your research."}
          </p>
          {register && (
            <label>
              Your name
              <input
                name="display_name"
                required
                maxLength={80}
                autoComplete="name"
                placeholder="Name"
              />
            </label>
          )}
          <label>
            Username
            <input
              name="username"
              required
              pattern="[a-zA-Z0-9_.-]{3,40}"
              title="3–40 letters, numbers, dots, hyphens, or underscores"
              autoComplete="username"
              placeholder="Username"
            />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              required
              minLength={10}
              maxLength={128}
              autoComplete={register ? "new-password" : "current-password"}
              placeholder="Password · 10+ characters"
            />
          </label>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <button className="primary wide" disabled={busy}>
            {busy ? "Opening…" : register ? "Create account" : "Enter LitLens"}{" "}
            <span aria-hidden="true">→</span>
          </button>
          <button
            type="button"
            className="text-button"
            disabled={busy}
            onClick={() => {
              setRegister(!register);
              setError("");
            }}
          >
            {register
              ? "Already registered? Sign in"
              : "New to LitLens? Create an account"}
          </button>
        </form>
      </section>
    </main>
  );
}
