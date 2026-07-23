import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  apiRequest,
  type ApiTokenRecord,
  type CreatedApiToken,
} from "../lib/api";

const tokensQueryKey = ["api-tokens"] as const;

export function TokensPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("ComfyUI");
  const [createdToken, setCreatedToken] = useState<string | null>(null);
  const tokens = useQuery({
    queryKey: tokensQueryKey,
    queryFn: () => apiRequest<ApiTokenRecord[]>("/api/v1/api-tokens"),
  });
  const createToken = useMutation({
    mutationFn: () =>
      apiRequest<CreatedApiToken>("/api/v1/api-tokens", {
        method: "POST",
        body: JSON.stringify({ label: name }),
      }),
    onSuccess: async (result) => {
      setCreatedToken(result.token);
      await queryClient.invalidateQueries({ queryKey: tokensQueryKey });
    },
  });
  const revokeToken = useMutation({
    mutationFn: (id: string) =>
      apiRequest<void>(`/api/v1/api-tokens/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: tokensQueryKey });
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreatedToken(null);
    createToken.mutate();
  }

  async function copyToken() {
    if (createdToken) {
      await navigator.clipboard.writeText(createdToken);
    }
  }

  return (
    <main className="page">
      <header className="page-header compact-header">
        <div>
          <p className="kicker">System</p>
          <h1>API tokens</h1>
          <p className="muted">
            Long-lived credentials for a future ComfyUI sender node or trusted
            local automation.
          </p>
        </div>
      </header>

      <section className="settings-grid">
        <article className="panel">
          <p className="kicker">New credential</p>
          <h2>Create a token</h2>
          <form className="inline-form" onSubmit={submit}>
            <label>
              Descriptive name
              <input
                value={name}
                maxLength={80}
                onChange={(event) => setName(event.target.value)}
                required
              />
            </label>
            <button
              className="primary-button"
              type="submit"
              disabled={createToken.isPending}
            >
              {createToken.isPending ? "Creating…" : "Create token"}
            </button>
          </form>
          {createdToken ? (
            <div className="token-reveal" role="status">
              <strong>Copy this token now</strong>
              <p>It is stored only as a hash and cannot be shown again.</p>
              <code>{createdToken}</code>
              <button className="secondary-button" type="button" onClick={copyToken}>
                Copy token
              </button>
            </div>
          ) : null}
          {createToken.isError ? (
            <p className="form-error" role="alert">
              Token creation failed. Check the API logs and try again.
            </p>
          ) : null}
        </article>

        <article className="panel">
          <div className="section-heading">
            <div>
              <p className="kicker">Issued credentials</p>
              <h2>Token history</h2>
            </div>
            <span className="document-count">
              {tokens.data?.filter((token) => !token.revoked_at).length ?? 0} active
            </span>
          </div>
          {tokens.isPending ? <p className="muted">Loading tokens…</p> : null}
          {tokens.isError ? (
            <p className="form-error" role="alert">
              Tokens could not be loaded.
            </p>
          ) : null}
          {tokens.data?.length === 0 ? (
            <div className="empty-state">
              <strong>No API tokens yet</strong>
              <p>Create one when a trusted local client needs access.</p>
            </div>
          ) : null}
          <div className="token-list">
            {tokens.data?.map((token) => (
              <div
                className="token-row"
                data-revoked={token.revoked_at ? "true" : "false"}
                key={token.id}
              >
                <span>
                  <strong>{token.label}</strong>
                  <small>
                    {token.token_prefix}… · Created{" "}
                    {new Date(token.created_at).toLocaleDateString()}
                    {token.revoked_at
                      ? ` · Revoked ${new Date(token.revoked_at).toLocaleDateString()}`
                      : ""}
                  </small>
                </span>
                {token.revoked_at ? (
                  <span className="revoked-badge">Revoked</span>
                ) : (
                  <button
                    className="danger-button"
                    type="button"
                    disabled={revokeToken.isPending}
                    onClick={() => revokeToken.mutate(token.id)}
                  >
                    Revoke
                  </button>
                )}
              </div>
            ))}
          </div>
        </article>
      </section>
    </main>
  );
}
