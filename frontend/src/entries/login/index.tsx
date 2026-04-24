import React from 'react';
import ReactDOM from 'react-dom/client';
import '../../index.css';

// Declare global for the injected context
declare global {
  interface Window {
    next_path?: string;
    login_error_key_json?: string | null;
    panel_build_label?: string;
  }
}

function LoginApp() {
  const loginErrorKey = window.login_error_key_json;
  const nextPath = window.next_path || '/admin';

  let errorMessage = '';
  if (loginErrorKey) {
    if (loginErrorKey.includes('invalidCredentials')) {
      errorMessage = 'Invalid username or password.';
    } else {
      errorMessage = 'An error occurred during login.';
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-slate-50 relative">
      <div className="absolute top-4 right-4 text-sm text-slate-400">
        FRP Network Evaluation {window.panel_build_label && `- build ${window.panel_build_label}`}
      </div>
      <div className="w-full max-w-md bg-white rounded-lg shadow-xl outline outline-1 outline-slate-200 p-8 space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Control Panel Login</h1>
          <p className="text-sm text-slate-500 mt-2">Enter your credentials to access the admin dashboard</p>
        </div>

        {errorMessage && (
          <div className="bg-red-50 outline outline-1 outline-red-200 text-red-600 text-sm p-3 rounded-md">
            {errorMessage}
          </div>
        )}

        <form method="POST" action="/login" className="space-y-4">
          <input type="hidden" name="next" value={nextPath} />
          <div className="space-y-2">
            <label htmlFor="username" className="text-sm font-medium text-slate-700 leading-none">Username</label>
            <input
              id="username"
              type="text"
              name="username"
              required
              autoComplete="username"
              autoFocus
              className="flex h-10 w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              placeholder="admin"
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="password" className="text-sm font-medium text-slate-700 leading-none">Password</label>
            <input
              id="password"
              type="password"
              name="password"
              required
              autoComplete="current-password"
              className="flex h-10 w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>
          <button
            type="submit"
            className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ring-offset-background bg-slate-900 text-white hover:bg-slate-900/90 h-10 py-2 px-4 w-full mt-2"
          >
            Sign In
          </button>
        </form>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <LoginApp />
  </React.StrictMode>
);
