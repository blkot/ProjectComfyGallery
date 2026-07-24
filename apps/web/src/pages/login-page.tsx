import { FormEvent, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Navigate, useNavigate } from "react-router";

import { sessionQueryKey, useSession } from "../features/auth/use-session";
import {
  ApiClientError,
  apiRequest,
  type SessionResponse,
} from "../lib/api";

export function LoginPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const session = useSession();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");

  const login = useMutation({
    mutationFn: () =>
      apiRequest<SessionResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      }),
    onSuccess: (result) => {
      queryClient.setQueryData(sessionQueryKey, result);
      navigate("/dashboard", { replace: true });
    },
  });

  if (session.data) {
    return <Navigate to="/dashboard" replace />;
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    login.mutate();
  }

  const message =
    login.error instanceof ApiClientError
      ? login.error.message
      : login.isError
        ? "The server could not be reached."
        : null;

  return (
    <main className="login-page">
      <section className="login-intro">
        <div className="eyebrow">Evidence over instinct</div>
        <h1>
          Your ComfyUI output,
          <br />
          finally <em>understood.</em>
        </h1>
        <p>
          Preserve every embedded workflow, review without bias, and discover
          which checkpoints and LoRA series actually work for you.
        </p>
        <div className="signal-card">
          <span className="signal-line" />
          <span className="signal-line signal-line-short" />
          <span className="signal-dot" />
          <small>Private by design · Built for your NAS</small>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-form-wrap">
          <div className="brand login-brand">
            <span className="brand-mark">CG</span>
            <strong>ComfyGallery</strong>
          </div>
          <div>
            <p className="kicker">Welcome back</p>
            <h2>Open your workspace</h2>
            <p className="muted">
              Sign in with the administrator account configured on this server.
            </p>
          </div>
          <form onSubmit={submit}>
            <label>
              Username
              <input
                autoComplete="username"
                name="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
              />
            </label>
            <label>
              Password
              <input
                autoComplete="current-password"
                name="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </label>
            {message ? (
              <p className="form-error" role="alert">
                {message}
              </p>
            ) : null}
            <button
              className="primary-button"
              type="submit"
              disabled={login.isPending}
            >
              {login.isPending ? "Signing in…" : "Sign in"}
            </button>
          </form>
          <p className="login-help">
            First run? Set <code>CG_ADMIN_PASSWORD</code> in your environment.
          </p>
        </div>
      </section>
    </main>
  );
}
