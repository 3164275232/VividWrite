import { useState, useEffect } from "react";
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
      <div className="login-hero-title" aria-hidden="true">
        Welcome to Vividwrite 2.0
      </div>
      <section className="login-card" aria-labelledby="login-title">

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
                <svg
                  viewBox="0 0 24 24"
                  width="19"
                  height="19"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="12" cy="8" r="4" />
                  <path d="M4 20c1.4-4 14.6-4 16 0" />
                </svg>
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
            <button type="submit">Log in</button>
          </div>
        </form>
      </section>
    </main>
  );
}
