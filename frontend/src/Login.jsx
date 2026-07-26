import { useState, useEffect } from "react";
import { ArrowRight, Eye, EyeOff, LockKeyhole, UserRound } from "lucide-react";
import "./Login.css";

export default function Login({ onLogin, passwordRequired = true }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // Temporarily disable scrollbars while login screen is active
  useEffect(() => {
    document.documentElement.classList.add("no-scroll");
    document.body.classList.add("no-scroll");
    return () => {
      document.documentElement.classList.remove("no-scroll");
      document.body.classList.remove("no-scroll");
    };
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const trimmed = username.trim();
    if (!trimmed) {
      setError("Username required");
      return;
    }
    if (passwordRequired && !password) {
      setError("Password required");
      return;
    }

    setError("");
    setIsSubmitting(true);
    try {
      await onLogin(trimmed, password);
    } catch (loginError) {
      setError(loginError?.message || "Login failed");
    } finally {
      setIsSubmitting(false);
    }
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
            <p>Sign in with the test account assigned to you.</p>
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
          </div>

          {passwordRequired && (
            <div className="field-group">
              <label htmlFor="password-input">Password</label>
              <div className="input-wrapper">
                <span className="input-icon" aria-hidden="true">
                  <LockKeyhole size={18} strokeWidth={1.8} />
                </span>
                <input
                  id="password-input"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Please enter the shared password"
                  aria-invalid={!!error}
                  aria-describedby={error ? "login-error" : undefined}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="password-visibility"
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  title={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
            </div>
          )}

          <p
            id="login-error"
            className="error-msg"
            role="alert"
            aria-live="assertive"
          >
            {error}
          </p>

          <div className="actions">
            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Signing in..." : "Open workspace"}
              {!isSubmitting && <ArrowRight size={16} />}
            </button>
          </div>
        </form>
        </section>
        <p className="login-footnote">Your local project data stays in this research workspace.</p>
      </div>
    </main>
  );
}
