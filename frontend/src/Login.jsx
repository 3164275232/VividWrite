import { useState, useEffect } from "react";
import { ArrowRight, UserRound } from "lucide-react";
import "./Login.css";

export default function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [error, setError] = useState("");

  // Temporarily disable scrollbars while login screen is active
  useEffect(() => {
    document.documentElement.classList.add("no-scroll");
    document.body.classList.add("no-scroll");
    return () => {
      document.documentElement.classList.remove("no-scroll");
      document.body.classList.remove("no-scroll");
    };
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = username.trim();
    if (!trimmed) {
      setError("Username required");
      return;
    }
    setError("");
    onLogin(trimmed);
  };

  return (
    <main className="login-root">
      <div className="login-shell">
        <header className="login-brand">
          <span className="login-brand-mark">V</span>
          <span>
            <strong>VividWrite</strong>
            <small>IELTS Writing Studio</small>
          </span>
        </header>
        <section className="login-card" aria-labelledby="login-title">
          <div className="login-header">
            <span className="login-kicker">Welcome back</span>
            <h1 id="login-title">Continue your writing practice</h1>
            <p>Enter your username to open your Task 1 workspace.</p>
          </div>
        <form
          className="login-form-wrapper"
          onSubmit={handleSubmit}
          noValidate
        >
          <div className="field-group">
            <label htmlFor="username-input">Username</label>
            <div className="input-wrapper">
              <span
                className="input-icon"
                aria-hidden="true"
              >
                <UserRound size={18} strokeWidth={1.8} />
              </span>
              <input
                id="username-input"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Please enter your username"
                aria-invalid={!!error}
                aria-describedby={error ? "username-error" : undefined}
                autoComplete="username"
                autoFocus
              />
            </div>
            <p
              id="username-error"
              className="error-msg"
              role="alert"
              aria-live="assertive"
            >
              {error}
            </p>
          </div>

          <div className="actions">
            <button type="submit">Open workspace <ArrowRight size={16} /></button>
          </div>
        </form>
        </section>
        <p className="login-footnote">Your local project data stays in this research workspace.</p>
      </div>
    </main>
  );
}
