import { Link } from "react-router";

export function NotFoundPage() {
  return (
    <main className="not-found">
      <p className="kicker">404</p>
      <h1>That frame is missing.</h1>
      <p>The page does not exist or has not been built yet.</p>
      <Link className="primary-button link-button" to="/dashboard">
        Return to workspace
      </Link>
    </main>
  );
}
