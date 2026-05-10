import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Shield, Zap, AlertTriangle, CheckCircle, Clock, Play,
  LogOut, ChevronRight, Globe, Code, Database,
  Cpu, Cloud, Lock, Eye, EyeOff, BarChart3, ArrowLeft, X, Menu, Plus,
  Users, Ban, Trash2, RefreshCw, ExternalLink, Star,
} from 'lucide-react';
import { supabase } from './supabase';
import { ErrorBoundary } from './ErrorBoundary';
import type { User } from '@supabase/supabase-js';

const AUDIT_API = import.meta.env.VITE_AUDIT_API_URL ?? '';

// ─── Types ────────────────────────────────────────────────────────────────────

type Page =
  | 'landing'
  | 'login'
  | 'signup'
  | 'dashboard'
  | 'evaluation'
  | 'audit-results'
  | 'admin';

interface UserProfile {
  id: string;
  email: string;
  role: 'admin' | 'user';
  email_verified: boolean;
  created_at: string;
  last_login?: string;
  is_blocked: boolean;
  blocked_reason?: string;
}

interface AuditUpdate {
  type: string;
  [key: string]: unknown;
}

interface Issue {
  id: string;
  agent_name: string;
  issue_category: string;
  specific_issue_detail: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  affected_url?: string;
  remediation_suggestion?: string;
}

interface Site {
  id: string;
  site_url: string;
  site_name?: string;
  created_at: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function severityBorder(s: string) {
  switch (s) {
    case 'critical': return 'border-red-500 bg-red-50 text-red-800';
    case 'high':     return 'border-orange-500 bg-orange-50 text-orange-800';
    case 'medium':   return 'border-yellow-500 bg-yellow-50 text-yellow-800';
    case 'low':      return 'border-blue-500 bg-blue-50 text-blue-800';
    default:         return 'border-gray-300 bg-gray-50 text-gray-700';
  }
}

function severityBadge(s: string) {
  switch (s) {
    case 'critical': return 'bg-red-600 text-white';
    case 'high':     return 'bg-orange-500 text-white';
    case 'medium':   return 'bg-yellow-500 text-white';
    case 'low':      return 'bg-blue-600 text-white';
    default:         return 'bg-gray-400 text-white';
  }
}

function agentLabel(name: string) {
  const map: Record<string, string> = {
    ghost_navigator:   'Ghost Navigator',
    mirror_stylist:    'Mirror Stylist',
    vault_counsel:     'Vault Counsel',
    fact_checker:      'Fact Checker',
    fortress_sentry:   'Fortress Sentry',
    vision_architect:  'Vision Architect',
  };
  return map[name] ?? name;
}

function agentGlyph(name: string) {
  const map: Record<string, string> = {
    ghost_navigator:   '◎',
    mirror_stylist:    '◈',
    vault_counsel:     '◆',
    fact_checker:      '◉',
    fortress_sentry:   '▣',
    vision_architect:  '◐',
  };
  return map[name] ?? '●';
}

// Reusable password input with eye toggle
function PasswordInput({
  value,
  onChange,
  onKeyDown,
  placeholder,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  placeholder?: string;
  className?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <input
        type={show ? 'text' : 'password'}
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        className={`pr-10 ${className ?? 'w-full bg-gray-100 border border-blue-200 text-gray-900 px-4 py-2.5 rounded-lg text-sm focus:outline-none focus:border-teal-500 placeholder-gray-400 transition'}`}
      />
      <button
        type="button"
        onClick={() => setShow(v => !v)}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-700 transition"
        aria-label={show ? 'Hide password' : 'Show password'}
      >
        {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
      </button>
    </div>
  );
}

// Settings icon for TECH_CATEGORIES
function SettingsIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

// ─── Nav ──────────────────────────────────────────────────────────────────────

function Nav({
  page,
  profile,
  onNavigate,
  onLogout,
}: {
  page: Page;
  profile: UserProfile | null;
  onNavigate: (p: Page) => void;
  onLogout: () => void;
}) {
  console.log('[Nav] render — page:', page, 'profile:', profile?.email ?? 'none');
  const [open, setOpen] = useState(false);
  const homeTarget: Page = !profile ? 'landing' : profile.role === 'admin' ? 'admin' : 'dashboard';

  return (
    <nav className="bg-white border-b border-blue-100 sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-16">
          <button onClick={() => onNavigate(homeTarget)} className="flex items-center gap-2 group">
            <Shield className="w-7 h-7 text-teal-600 group-hover:text-teal-700 transition" />
            <span className="text-gray-900 font-bold text-xl tracking-tight">Shield Agent</span>
            <span className="hidden sm:inline text-xs bg-teal-100 text-teal-700 px-2 py-0.5 rounded-full font-medium">Crew</span>
          </button>

          <div className="hidden md:flex items-center gap-4">
            {profile ? (
              <>
                <span className="text-gray-500 text-sm truncate max-w-48">{profile.email}</span>
                {profile.role === 'admin' && (
                  <button
                    onClick={() => onNavigate('admin')}
                    className={`text-sm px-3 py-1.5 rounded-lg transition ${page === 'admin' ? 'bg-teal-600 text-white' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'}`}
                  >
                    Admin
                  </button>
                )}
                <button
                  onClick={() => onNavigate('dashboard')}
                  className={`text-sm px-3 py-1.5 rounded-lg transition ${page === 'dashboard' ? 'bg-teal-600 text-white' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'}`}
                >
                  Dashboard
                </button>
                <button onClick={onLogout} className="flex items-center gap-1.5 text-gray-400 hover:text-red-500 text-sm transition">
                  <LogOut className="w-4 h-4" />
                  Logout
                </button>
              </>
            ) : (
              <>
                <button onClick={() => onNavigate('login')} className="text-gray-600 hover:text-gray-900 text-sm transition px-3 py-1.5 rounded-lg hover:bg-gray-100">Sign In</button>
                <button onClick={() => onNavigate('signup')} className="bg-teal-600 hover:bg-teal-500 text-white text-sm px-4 py-1.5 rounded-lg transition font-medium">Sign Up</button>
              </>
            )}
          </div>

          <button className="md:hidden text-gray-500 hover:text-gray-900 p-1 rounded" onClick={() => setOpen(v => !v)}>
            {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {open && (
        <div className="md:hidden border-t border-blue-100 bg-white px-4 py-3 space-y-2">
          {profile ? (
            <>
              <p className="text-gray-400 text-xs truncate">{profile.email}</p>
              {profile.role === 'admin' && (
                <button onClick={() => { onNavigate('admin'); setOpen(false); }} className="block text-gray-700 hover:text-gray-900 text-sm py-1.5">Admin Dashboard</button>
              )}
              <button onClick={() => { onNavigate('dashboard'); setOpen(false); }} className="block text-gray-700 hover:text-gray-900 text-sm py-1.5">Dashboard</button>
              <button onClick={() => { onLogout(); setOpen(false); }} className="block text-red-500 text-sm py-1.5">Logout</button>
            </>
          ) : (
            <>
              <button onClick={() => { onNavigate('login'); setOpen(false); }} className="block text-gray-700 text-sm py-1.5">Sign In</button>
              <button onClick={() => { onNavigate('signup'); setOpen(false); }} className="block text-teal-600 font-medium text-sm py-1.5">Sign Up</button>
            </>
          )}
        </div>
      )}
    </nav>
  );
}

// ─── Landing Page ─────────────────────────────────────────────────────────────

function LandingPage({ onNavigate }: { onNavigate: (p: Page) => void }) {
  console.log('[LandingPage] render');
  const agents = [
    { icon: <Eye className="w-6 h-6 text-teal-600" />, name: 'Ghost Navigator', desc: 'BFS traversal tests every route, form, and interaction for broken links and dead-ends.' },
    { icon: <Star className="w-6 h-6 text-pink-500" />, name: 'Mirror Stylist', desc: 'Detects contrast failures, z-index collisions, font jumps, and mobile overflow.' },
    { icon: <Lock className="w-6 h-6 text-amber-500" />, name: 'Vault Counsel', desc: 'Cross-references site text against your policy PDFs, flags GDPR issues and dark patterns.' },
    { icon: <CheckCircle className="w-6 h-6 text-green-500" />, name: 'Fact Checker', desc: 'Verifies every external link, audits testimonials for authenticity, flags broken citations.' },
    { icon: <Shield className="w-6 h-6 text-red-500" />, name: 'Fortress Sentry', desc: 'Scans console logs for leaked secrets, checks EXIF metadata, verifies field masking.' },
    { icon: <BarChart3 className="w-6 h-6 text-blue-500" />, name: 'Vision Architect', desc: 'Evaluates reading level, tone consistency, and generates conversion-focused enhancements.' },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-white via-teal-50/30 to-white">
      <section className="max-w-5xl mx-auto px-6 pt-24 pb-16 text-center">
        <div className="inline-flex items-center gap-2 bg-teal-50 border border-teal-200 text-teal-700 text-xs px-3 py-1.5 rounded-full mb-6 font-medium">
          <Zap className="w-3.5 h-3.5" />
          Autonomous Walk-Through Audit Platform
        </div>
        <h1 className="text-5xl sm:text-6xl font-extrabold text-gray-900 leading-tight mb-6">
          Your site, audited by<br />
          <span className="text-teal-600">a 6-agent crew</span>
        </h1>
        <p className="text-lg text-gray-500 max-w-2xl mx-auto mb-10">
          Shield Agent autonomously crawls your website, simulates real users, and surfaces UX, security, compliance, and design issues — live, in real-time.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <button onClick={() => onNavigate('signup')} className="bg-teal-600 hover:bg-teal-500 text-white font-semibold px-8 py-3.5 rounded-xl transition flex items-center gap-2 justify-center shadow-sm hover:shadow-md">
            Get Started Free <ChevronRight className="w-5 h-5" />
          </button>
          <button onClick={() => onNavigate('login')} className="border border-gray-200 hover:border-gray-400 text-gray-600 hover:text-gray-900 font-semibold px-8 py-3.5 rounded-xl transition hover:shadow-sm">
            Sign In
          </button>
        </div>
      </section>

      <section className="border-y border-gray-100 bg-white/60 backdrop-blur-sm">
        <div className="max-w-4xl mx-auto grid grid-cols-2 sm:grid-cols-4 divide-x divide-y sm:divide-y-0 divide-gray-100">
          {[
            { label: 'Issue Types Detected', value: '27+' },
            { label: 'Crew Agents', value: '6' },
            { label: 'Database Tables', value: '34' },
            { label: 'Real-Time Streaming', value: 'WS' },
          ].map(s => (
            <div key={s.label} className="text-center py-8 px-4">
              <div className="text-3xl font-extrabold text-teal-600">{s.value}</div>
              <div className="text-sm text-gray-500 mt-1">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="max-w-5xl mx-auto px-6 py-20">
        <h2 className="text-2xl font-bold text-gray-900 text-center mb-12">
          Six specialized agents, one comprehensive audit
        </h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {agents.map(a => (
            <div key={a.name} className="bg-white border border-gray-200 rounded-xl p-6 hover:border-teal-300 hover:shadow-md transition">
              <div className="mb-4">{a.icon}</div>
              <h3 className="font-semibold text-gray-900 mb-2">{a.name}</h3>
              <p className="text-gray-500 text-sm leading-relaxed">{a.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="max-w-2xl mx-auto px-6 pb-24 text-center">
        <div className="bg-gradient-to-br from-teal-50 to-blue-50 border border-teal-200 rounded-2xl p-10">
          <h2 className="text-2xl font-bold text-gray-900 mb-3">Ready to audit your site?</h2>
          <p className="text-gray-500 mb-6">Create a free account and run your first audit in minutes.</p>
          <button onClick={() => onNavigate('signup')} className="bg-teal-600 hover:bg-teal-500 text-white font-semibold px-8 py-3 rounded-xl transition shadow-sm hover:shadow-md">
            Create Your Account
          </button>
        </div>
      </section>
    </div>
  );
}

// ─── Login Page ───────────────────────────────────────────────────────────────

function LoginPage({
  onNavigate,
  onLogin,
}: {
  onNavigate: (p: Page) => void;
  onLogin: (profile: UserProfile) => void;
}) {
  console.log('[LoginPage] render');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async () => {
    if (!email || !password) { setError('Please fill in all fields.'); return; }
    setLoading(true);
    setError('');
    try {
      console.log('[LoginPage] attempting signInWithPassword');
      const { data, error: authErr } = await supabase.auth.signInWithPassword({ email, password });
      if (authErr) { console.error('[LoginPage] authErr:', authErr); setError(authErr.message); return; }
      if (!data.user) { setError('Login failed. Please try again.'); return; }

      await supabase.from('users').update({ last_login: new Date().toISOString() }).eq('id', data.user.id);

      const { data: profile, error: profileErr } = await supabase.from('users').select('*').eq('id', data.user.id).maybeSingle();
      if (profileErr) console.error('[LoginPage] profileErr:', profileErr);

      if (!profile) {
        const newProfile: UserProfile = {
          id: data.user.id,
          email: data.user.email ?? email,
          role: data.user.email === 'shivakumarkannan2006@gmail.com' ? 'admin' : 'user',
          email_verified: !!data.user.email_confirmed_at,
          created_at: new Date().toISOString(),
          is_blocked: false,
        };
        const { error: upsertErr } = await supabase.from('users').upsert(newProfile);
        if (upsertErr) console.error('[LoginPage] upsertErr:', upsertErr);
        onLogin(newProfile);
      } else {
        onLogin(profile as UserProfile);
      }
    } catch (err) {
      console.error('[LoginPage] unexpected error:', err);
      setError('An unexpected error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-white to-teal-50/30 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Shield className="w-12 h-12 text-teal-600 mx-auto mb-3" />
          <h1 className="text-2xl font-bold text-gray-900">Welcome back</h1>
          <p className="text-gray-500 text-sm mt-1">Sign in to your Shield Agent account</p>
        </div>

        <div className="bg-white border border-gray-200 rounded-2xl p-8 space-y-5 shadow-sm">
          {error && (
            <div role="alert" className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">{error}</div>
          )}

          <div>
            <label className="block text-gray-700 text-sm font-medium mb-1.5" htmlFor="login-email">Email address</label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleLogin()}
              placeholder="you@example.com"
              className="w-full bg-gray-50 border border-gray-200 text-gray-900 px-4 py-2.5 rounded-lg text-sm focus:outline-none focus:border-teal-500 placeholder-gray-400 transition"
            />
          </div>

          <div>
            <label className="block text-gray-700 text-sm font-medium mb-1.5" htmlFor="login-password">Password</label>
            <PasswordInput
              value={password}
              onChange={setPassword}
              onKeyDown={e => e.key === 'Enter' && handleLogin()}
              placeholder="••••••••"
            />
          </div>

          <button
            onClick={handleLogin}
            disabled={loading}
            aria-busy={loading}
            className="w-full bg-teal-600 hover:bg-teal-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded-lg transition"
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>

          <p className="text-center text-gray-500 text-sm">
            No account?{' '}
            <button onClick={() => onNavigate('signup')} className="text-teal-600 hover:text-teal-700 font-medium">Create one</button>
          </p>
        </div>
      </div>
    </div>
  );
}

// ─── Signup Page ──────────────────────────────────────────────────────────────

function SignupPage({
  onNavigate,
  onLogin,
}: {
  onNavigate: (p: Page) => void;
  onLogin: (profile: UserProfile) => void;
}) {
  console.log('[SignupPage] render');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSignup = async () => {
    if (!email || !password) { setError('Please fill in all fields.'); return; }
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return; }
    if (!/[A-Z]/.test(password)) { setError('Password must contain at least one uppercase letter.'); return; }
    if (!/[0-9]/.test(password)) { setError('Password must contain at least one number.'); return; }

    setLoading(true);
    setError('');
    try {
      console.log('[SignupPage] calling auth.signUp for', email);
      const { data, error: authErr } = await supabase.auth.signUp({ email, password });

      if (authErr) { console.error('[SignupPage] authErr:', authErr); setError(authErr.message); return; }
      if (!data.user) { setError('Signup failed. Please try again.'); return; }

      console.log('[SignupPage] auth.signUp succeeded, user id:', data.user.id);

      // Give trigger a moment then fetch profile
      const { data: profile, error: profileErr } = await supabase
        .from('users')
        .select('*')
        .eq('id', data.user.id)
        .maybeSingle();

      if (profileErr) console.error('[SignupPage] profile fetch err:', profileErr);

      if (profile) {
        console.log('[SignupPage] trigger created profile:', profile);
        onLogin(profile as UserProfile);
      } else {
        // Trigger may not have fired yet — build a local profile and upsert
        console.warn('[SignupPage] profile not found after signup, upserting manually');
        const fallback: UserProfile = {
          id: data.user.id,
          email: data.user.email ?? email,
          role: data.user.email === 'shivakumarkannan2006@gmail.com' ? 'admin' : 'user',
          email_verified: false,
          created_at: new Date().toISOString(),
          is_blocked: false,
        };
        const { error: upsertErr } = await supabase.from('users').upsert(fallback, { onConflict: 'id' });
        if (upsertErr) {
          // RLS may block the upsert if session isn't fully ready; proceed with local profile
          console.warn('[SignupPage] fallback upsert blocked (likely RLS timing), proceeding with local profile:', upsertErr.message);
        }
        onLogin(fallback);
      }
    } catch (err) {
      console.error('[SignupPage] unexpected error:', err);
      setError('An unexpected error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-white to-teal-50/30 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Shield className="w-12 h-12 text-teal-600 mx-auto mb-3" />
          <h1 className="text-2xl font-bold text-gray-900">Create your account</h1>
          <p className="text-gray-500 text-sm mt-1">Start auditing your site with Shield Agent</p>
        </div>

        <div className="bg-white border border-gray-200 rounded-2xl p-8 space-y-5 shadow-sm">
          {error && (
            <div role="alert" className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">{error}</div>
          )}

          <div>
            <label className="block text-gray-700 text-sm font-medium mb-1.5" htmlFor="signup-email">Email address</label>
            <input
              id="signup-email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full bg-gray-50 border border-gray-200 text-gray-900 px-4 py-2.5 rounded-lg text-sm focus:outline-none focus:border-teal-500 placeholder-gray-400 transition"
            />
          </div>

          <div>
            <label className="block text-gray-700 text-sm font-medium mb-1.5" htmlFor="signup-password">Password</label>
            <PasswordInput
              value={password}
              onChange={setPassword}
              onKeyDown={e => e.key === 'Enter' && handleSignup()}
              placeholder="Min 8 chars, 1 uppercase, 1 number"
            />
            <p className="text-gray-400 text-xs mt-1.5">At least 8 characters, one uppercase letter, one digit</p>
          </div>

          <button
            onClick={handleSignup}
            disabled={loading}
            aria-busy={loading}
            className="w-full bg-teal-600 hover:bg-teal-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded-lg transition"
          >
            {loading ? 'Creating account…' : 'Create Account'}
          </button>

          <p className="text-center text-gray-500 text-sm">
            Already have an account?{' '}
            <button onClick={() => onNavigate('login')} className="text-teal-600 hover:text-teal-700 font-medium">Sign in</button>
          </p>
        </div>
      </div>
    </div>
  );
}

// ─── User Dashboard ───────────────────────────────────────────────────────────

function DashboardPage({
  profile,
  onNavigate,
}: {
  profile: UserProfile;
  onNavigate: (p: Page) => void;
}) {
  console.log('[DashboardPage] render — user:', profile.email);
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(true);
  // activeSiteId: which site row is expanded with audit tabs
  const [activeSiteId, setActiveSiteId] = useState<string | null>(null);

  useEffect(() => {
    console.log('[DashboardPage] fetching user_sites for', profile.id);
    supabase
      .from('user_sites')
      .select('id, site_url, site_name, created_at')
      .eq('user_id', profile.id)
      .order('created_at', { ascending: false })
      .then(({ data, error }) => {
        if (error) console.error('[DashboardPage] sites fetch error:', error);
        setSites((data as Site[]) ?? []);
        setLoading(false);
      });
  }, [profile.id]);

  // Group sites by base URL (same domain = same group, shown as tabs)
  const grouped = sites.reduce<Record<string, Site[]>>((acc, s) => {
    let base = s.site_url;
    try { base = new URL(s.site_url).hostname; } catch { /* keep raw */ }
    (acc[base] = acc[base] ?? []).push(s);
    return acc;
  }, {});

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-8">
      <div className="max-w-5xl mx-auto">

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
            <p className="text-gray-400 text-sm mt-0.5">{profile.email}</p>
          </div>
        </div>

        {/* Big + New Site Evaluation CTA */}
        <button
          onClick={() => onNavigate('evaluation')}
          className="w-full mb-8 flex items-center justify-center gap-3 bg-teal-600 hover:bg-teal-500 active:bg-teal-700 text-white font-semibold py-5 rounded-2xl transition shadow-sm hover:shadow-md text-lg group"
        >
          <div className="w-9 h-9 bg-white/20 group-hover:bg-white/30 rounded-full flex items-center justify-center transition">
            <Plus className="w-5 h-5" />
          </div>
          New Site Evaluation
        </button>

        {/* Stats row */}
        <div className="mb-8">
          <div className="bg-white border border-gray-200 rounded-xl p-5 inline-block">
            <p className="text-gray-400 text-xs font-medium mb-1">Sites Audited</p>
            <p className="text-3xl font-bold text-gray-900">{sites.length}</p>
          </div>
        </div>

        {/* Sites list */}
        <div>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">Your Audited Sites</h2>

          {loading ? (
            <div className="flex items-center justify-center py-16 text-gray-400 text-sm gap-2">
              <RefreshCw className="w-4 h-4 animate-spin" /> Loading sites…
            </div>
          ) : sites.length === 0 ? (
            <div className="bg-white border-2 border-dashed border-gray-200 rounded-2xl p-16 text-center">
              <div className="w-16 h-16 bg-teal-50 rounded-full flex items-center justify-center mx-auto mb-4">
                <Globe className="w-8 h-8 text-teal-400" />
              </div>
              <p className="text-gray-700 font-semibold text-lg mb-1">No sites audited yet</p>
              <p className="text-gray-400 text-sm mb-6">Click the button above to evaluate your first site.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {Object.entries(grouped).map(([hostname, groupSites]) => {
                const isExpanded = activeSiteId === hostname;
                const latest = groupSites[0];
                return (
                  <div key={hostname} className="bg-white border border-gray-200 rounded-xl overflow-hidden hover:border-teal-300 transition">
                    {/* Site row header */}
                    <button
                      className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-gray-50 transition"
                      onClick={() => setActiveSiteId(isExpanded ? null : hostname)}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-9 h-9 bg-teal-50 rounded-lg flex items-center justify-center flex-shrink-0">
                          <Globe className="w-5 h-5 text-teal-600" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-gray-900 font-semibold truncate">{latest.site_name || hostname}</p>
                          <p className="text-gray-400 text-xs truncate">{latest.site_url}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 flex-shrink-0 ml-4">
                        {groupSites.length > 1 && (
                          <span className="text-xs bg-teal-100 text-teal-700 px-2 py-0.5 rounded-full font-medium">{groupSites.length} audits</span>
                        )}
                        <ChevronRight className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                      </div>
                    </button>

                    {/* Expanded: tabs for each audit run */}
                    {isExpanded && (
                      <div className="border-t border-gray-100 px-5 pb-4">
                        <div className="flex gap-2 pt-3 overflow-x-auto pb-1">
                          {groupSites.map((s, idx) => (
                            <button
                              key={s.id}
                              onClick={() => onNavigate('audit-results')}
                              className="flex-shrink-0 flex items-center gap-2 bg-gray-50 hover:bg-teal-50 border border-gray-200 hover:border-teal-300 text-gray-600 hover:text-teal-700 px-4 py-2 rounded-lg text-sm transition"
                            >
                              <Clock className="w-3.5 h-3.5" />
                              Audit {groupSites.length - idx} — {new Date(s.created_at).toLocaleDateString()}
                              <ExternalLink className="w-3.5 h-3.5 opacity-60" />
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Evaluation Page ──────────────────────────────────────────────────────────

const TECH_CATEGORIES = [
  {
    key: 'AI Site Builders',
    icon: <Zap className="w-4 h-4" />,
    options: ['Lovable', 'Bolt.new', 'Base44', 'v0 by Vercel'],
  },
  {
    key: 'Code Editors & AI Coding',
    icon: <Code className="w-4 h-4" />,
    options: ['Cursor', 'Windsurf', 'VS Code + Copilot', 'GitHub Copilot', 'Replit'],
  },
  {
    key: 'Databases',
    icon: <Database className="w-4 h-4" />,
    options: ['Supabase', 'Firebase', 'MongoDB', 'PostgreSQL', 'MySQL', 'Redis'],
  },
  {
    key: 'Frontend Frameworks',
    icon: <Globe className="w-4 h-4" />,
    options: ['React', 'Next.js'],
  },
  {
    key: 'Backend & APIs',
    icon: <SettingsIcon className="w-4 h-4" />,
    options: ['Node.js', 'Express', 'FastAPI'],
  },
  {
    key: 'AI & LLM Services',
    icon: <Cpu className="w-4 h-4" />,
    options: ['OpenAI', 'Gemini', 'Anthropic Claude', 'LangChain'],
  },
  {
    key: 'Hosting & Deployment',
    icon: <Cloud className="w-4 h-4" />,
    options: ['Vercel', 'Railway', 'Render', 'AWS', 'GitHub Pages / Cloudflare Pages'],
  },
  {
    key: 'Errors',
    icon: <AlertTriangle className="w-4 h-4" />,
    options: [],
  },
];

function EvaluationPage({
  profile,
  onNavigate,
  onStartAudit,
}: {
  profile: UserProfile;
  onNavigate: (p: Page) => void;
  onStartAudit: (url: string, siteName: string, siteId: string) => void;
}) {
  console.log('[EvaluationPage] render — user:', profile.email);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [url, setUrl] = useState('');
  const [siteName, setSiteName] = useState('');
  const [urlError, setUrlError] = useState('');
  const [saving, setSaving] = useState(false);

  const toggle = (opt: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(opt)) next.delete(opt); else next.add(opt);
      return next;
    });
  };

  const handleStart = async () => {
    setUrlError('');
    if (selected.size === 0) { setUrlError('Please select at least one technology.'); return; }
    if (!url) { setUrlError('Please enter your website URL.'); return; }
    try { new URL(url); } catch { setUrlError('Enter a valid URL (include https://).'); return; }

    setSaving(true);
    try {
      console.log('[EvaluationPage] inserting user_site for user:', profile.id, 'url:', url);
      const { data: site, error: siteErr } = await supabase
        .from('user_sites')
        .insert({ user_id: profile.id, site_url: url, site_name: siteName || url })
        .select('id')
        .single();

      if (siteErr) {
        console.error('[EvaluationPage] site insert error:', siteErr);
        setUrlError(siteErr.message || 'Failed to save site.');
        return;
      }

      if (!site?.id) {
        setUrlError('Failed to save site. Please try again.');
        return;
      }

      console.log('[EvaluationPage] site saved, id:', site.id);
      onStartAudit(url, siteName || url, site.id);
    } catch (err) {
      console.error('[EvaluationPage] unexpected error:', err);
      setUrlError('An unexpected error occurred.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-10">
      <div className="max-w-3xl mx-auto">
        <button onClick={() => onNavigate('dashboard')} className="flex items-center gap-2 text-gray-400 hover:text-gray-700 text-sm mb-8 transition">
          <ArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </button>

        <h1 className="text-2xl font-bold text-gray-900 mb-2">New Site Evaluation</h1>
        <p className="text-gray-400 text-sm mb-8">Select the technologies your site uses, then enter your URL to begin the audit.</p>

        {/* Step 1 */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-6 h-6 bg-teal-600 text-white rounded-full flex items-center justify-center text-xs font-bold">1</div>
            <h2 className="font-semibold text-gray-900">Select your tech stack</h2>
            {selected.size > 0 && (
              <span className="ml-auto text-xs bg-teal-100 text-teal-700 px-2 py-0.5 rounded-full font-medium">{selected.size} selected</span>
            )}
          </div>

          <div className="space-y-4">
            {TECH_CATEGORIES.map(cat => (
              <div key={cat.key} className="bg-white border border-gray-200 rounded-xl p-5">
                <div className="flex items-center gap-2 mb-3 text-gray-500">
                  {cat.icon}
                  <span className="font-medium text-sm">{cat.key}</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {cat.options.length === 0 ? (
                    <span className="text-gray-400 text-xs italic">Select this category to flag known errors</span>
                  ) : cat.options.map(opt => {
                    const active = selected.has(opt);
                    return (
                      <button
                        key={opt}
                        onClick={() => toggle(opt)}
                        className={`text-sm px-3 py-1.5 rounded-full border transition font-medium ${active ? 'bg-teal-600 border-teal-600 text-white' : 'border-gray-300 text-gray-600 hover:border-teal-400 hover:text-teal-700 hover:bg-teal-50'}`}
                      >
                        {active && <span className="mr-1 text-xs">✓</span>}
                        {opt}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Step 2 */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-6 h-6 bg-teal-600 text-white rounded-full flex items-center justify-center text-xs font-bold">2</div>
            <h2 className="font-semibold text-gray-900">Enter your website details</h2>
          </div>

          <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
            <div>
              <label className="block text-gray-600 text-sm font-medium mb-1.5" htmlFor="site-name">Site Name (optional)</label>
              <input
                id="site-name"
                type="text"
                value={siteName}
                onChange={e => setSiteName(e.target.value)}
                placeholder="My Awesome Project"
                className="w-full bg-gray-50 border border-gray-200 text-gray-900 px-4 py-2.5 rounded-lg text-sm focus:outline-none focus:border-teal-500 placeholder-gray-400 transition"
              />
            </div>
            <div>
              <label className="block text-gray-600 text-sm font-medium mb-1.5" htmlFor="site-url">Website URL</label>
              <input
                id="site-url"
                type="url"
                value={url}
                onChange={e => setUrl(e.target.value)}
                placeholder="https://your-site.com"
                className={`w-full bg-gray-50 border text-gray-900 px-4 py-2.5 rounded-lg text-sm focus:outline-none placeholder-gray-400 transition ${urlError ? 'border-red-400 focus:border-red-500' : 'border-gray-200 focus:border-teal-500'}`}
              />
              {urlError && <p role="alert" className="text-red-500 text-xs mt-2">{urlError}</p>}
              <p className="text-gray-400 text-xs mt-1.5">The crew will crawl this URL and all reachable sub-pages.</p>
            </div>
          </div>
        </div>

        <div className="flex gap-3">
          <button onClick={() => onNavigate('dashboard')} className="border border-gray-200 hover:border-gray-400 text-gray-500 hover:text-gray-900 px-5 py-2.5 rounded-lg text-sm transition">
            Cancel
          </button>
          <button
            onClick={handleStart}
            disabled={selected.size === 0 || !url || saving}
            aria-busy={saving}
            className="flex items-center gap-2 bg-teal-600 hover:bg-teal-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold px-6 py-2.5 rounded-lg text-sm transition"
          >
            <Play className="w-4 h-4" />
            {saving ? 'Saving…' : 'Start Audit'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Audit Results Page ───────────────────────────────────────────────────────

function AuditResultsPage({
  auditUrl,
  onNavigate,
}: {
  auditUrl: string;
  onNavigate: (p: Page) => void;
}) {
  console.log('[AuditResultsPage] render — auditUrl:', auditUrl);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState<{ status?: string; total_pages_discovered?: number }>({});
  const [issues, setIssues] = useState<Issue[]>([]);
  const [pages, setPages] = useState<{ url: string }[]>([]);
  const [activities, setActivities] = useState<AuditUpdate[]>([]);
  const [activeTab, setActiveTab] = useState<'activity' | 'issues' | 'pages'>('activity');
  const [backendUnavailable, setBackendUnavailable] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startAudit = useCallback(async () => {
    if (!auditUrl || !AUDIT_API) {
      console.warn('[AuditResultsPage] AUDIT_API not configured, VITE_AUDIT_API_URL=', AUDIT_API);
      setBackendUnavailable(true);
      return;
    }
    setRunning(true);
    setIssues([]);
    setPages([]);
    setActivities([]);
    try {
      const res = await fetch(`${AUDIT_API}/api/start-audit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_url: auditUrl, company_id: 'user-audit' }),
      });
      const data = await res.json();
      if (!data.audit_session_id) { setRunning(false); return; }
      setSessionId(data.audit_session_id);

      const wsUrl = AUDIT_API.replace('https://', 'wss://').replace('http://', 'ws://');
      const ws = new WebSocket(`${wsUrl}/ws/audit/${data.audit_session_id}`);
      ws.onmessage = e => {
        const msg: AuditUpdate = JSON.parse(e.data);
        setActivities(prev => [msg, ...prev.slice(0, 149)]);
        if (msg.type === 'audit_complete') setRunning(false);
      };
      wsRef.current = ws;

      const poll = setInterval(async () => {
        try {
          const [issR, pgR, stR] = await Promise.all([
            fetch(`${AUDIT_API}/api/audit/${data.audit_session_id}/issues`).then(r => r.json()),
            fetch(`${AUDIT_API}/api/audit/${data.audit_session_id}/pages`).then(r => r.json()),
            fetch(`${AUDIT_API}/api/audit/${data.audit_session_id}/status`).then(r => r.json()),
          ]);
          setIssues(issR.issues ?? []);
          setPages(pgR.pages ?? []);
          setStatus(stR);
          if (stR.status === 'completed' || stR.status === 'failed') {
            setRunning(false);
            clearInterval(poll);
          }
        } catch (err) {
          console.error('[AuditResultsPage] poll error:', err);
        }
      }, 2500);
      pollRef.current = poll;
    } catch (err) {
      console.error('[AuditResultsPage] startAudit error:', err);
      setBackendUnavailable(true);
      setRunning(false);
    }
  }, [auditUrl]);

  useEffect(() => {
    startAudit();
    return () => {
      wsRef.current?.close();
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [startAudit]);

  const criticalCount = issues.filter(i => i.severity === 'critical').length;
  const highCount = issues.filter(i => i.severity === 'high').length;
  const issuesByAgent = issues.reduce<Record<string, Issue[]>>((acc, iss) => {
    (acc[iss.agent_name] = acc[iss.agent_name] ?? []).push(iss);
    return acc;
  }, {});

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => onNavigate('dashboard')} className="text-gray-400 hover:text-gray-900 transition">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-bold text-gray-900 truncate">Audit: {auditUrl}</h1>
            <p className="text-gray-400 text-xs">{sessionId ? `Session ${sessionId.slice(0, 8)}…` : 'Starting…'}</p>
          </div>
          {running && (
            <div className="flex items-center gap-2 text-green-500 text-sm font-medium" aria-live="polite">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              Crew active
            </div>
          )}
          {!running && sessionId && <span className="text-gray-400 text-sm">Complete</span>}
        </div>

        {backendUnavailable && (
          <div role="alert" className="bg-amber-50 border border-amber-200 text-amber-800 rounded-xl p-5 mb-6">
            <p className="font-semibold mb-1">Audit engine not configured</p>
            <p className="text-sm">
              The crawling crew runs on a separate Python backend. Set{' '}
              <code className="bg-amber-100 px-1 rounded text-xs font-mono">VITE_AUDIT_API_URL</code>{' '}
              in your environment to point to a deployed backend, then rebuild.{' '}
              The site record has been saved to your dashboard.
            </p>
          </div>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          {[
            { label: 'Pages', value: status.total_pages_discovered ?? pages.length, color: 'text-teal-600' },
            { label: 'Issues', value: issues.length, color: 'text-red-500' },
            { label: 'Critical', value: criticalCount, color: 'text-red-600' },
            { label: 'High', value: highCount, color: 'text-orange-500' },
          ].map(c => (
            <div key={c.label} className="bg-white border border-gray-200 rounded-xl p-4">
              <p className="text-gray-400 text-xs mb-1">{c.label}</p>
              <p className={`text-3xl font-bold ${c.color}`}>{c.value}</p>
            </div>
          ))}
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <div className="flex border-b border-gray-200">
              {(['activity', 'issues', 'pages'] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-5 py-3 text-sm font-medium transition capitalize ${activeTab === tab ? 'border-b-2 border-teal-500 text-teal-600' : 'text-gray-400 hover:text-gray-700'}`}
                >
                  {tab === 'activity' ? 'Crew Activity' : tab === 'issues' ? `Issues (${issues.length})` : `Pages (${pages.length})`}
                </button>
              ))}
            </div>

            <div className="bg-white border border-gray-200 border-t-0 rounded-b-xl p-5 min-h-72">
              {activeTab === 'activity' && (
                <div className="space-y-2 max-h-96 overflow-y-auto" aria-live="polite">
                  {activities.length === 0 ? (
                    <div className="text-center py-12">
                      {running ? (
                        <div className="flex flex-col items-center gap-3">
                          <RefreshCw className="w-7 h-7 text-teal-500 animate-spin" />
                          <p className="text-gray-400 text-sm">Waiting for crew activity…</p>
                        </div>
                      ) : (
                        <p className="text-gray-400 text-sm">No activity recorded.</p>
                      )}
                    </div>
                  ) : (
                    activities.map((a, i) => {
                      const agent = a.agent ? (typeof a.agent === 'string' ? a.agent : JSON.stringify(a.agent)) : null;
                      const url = a.url ? (typeof a.url === 'string' ? a.url : JSON.stringify(a.url)) : null;
                      const message = a.message ? (typeof a.message === 'string' ? a.message : JSON.stringify(a.message)) : null;
                      return (
                        <div key={i} className="bg-gray-50 border border-gray-100 rounded-lg p-3 text-xs font-mono">
                          <span className="text-teal-600 font-semibold">{a.type}</span>
                          {agent && <span className="text-gray-400 ml-2">({agent})</span>}
                          {url && <div className="text-gray-500 truncate mt-0.5">{url}</div>}
                          {message && <div className="text-gray-600 mt-0.5">{message}</div>}
                        </div>
                      );
                    })
                  )}
                </div>
              )}

              {activeTab === 'issues' && (
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {issues.length === 0 ? (
                    <p className="text-gray-400 text-sm text-center py-12" aria-live="polite">
                      {running ? 'Scanning for issues…' : 'No issues found.'}
                    </p>
                  ) : (
                    issues.map((iss, i) => (
                      <div key={iss.id ?? i} className={`border-l-4 rounded-lg p-4 ${severityBorder(iss.severity)}`}>
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-mono text-sm opacity-50">{agentGlyph(iss.agent_name)}</span>
                              <span className="text-xs font-semibold opacity-70">{agentLabel(iss.agent_name)}</span>
                              <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ml-auto ${severityBadge(iss.severity)}`}>{iss.severity}</span>
                            </div>
                            <p className="text-sm">{iss.specific_issue_detail}</p>
                            {iss.affected_url && <p className="text-xs opacity-50 truncate mt-1">{iss.affected_url}</p>}
                            {iss.remediation_suggestion && (
                              <p className="text-xs opacity-60 mt-2 border-t border-current/20 pt-2">Fix: {iss.remediation_suggestion}</p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {activeTab === 'pages' && (
                <div className="space-y-1.5 max-h-96 overflow-y-auto">
                  {pages.length === 0 ? (
                    <p className="text-gray-400 text-sm text-center py-12" aria-live="polite">
                      {running ? 'Discovering pages…' : 'No pages discovered.'}
                    </p>
                  ) : (
                    pages.map((p, i) => (
                      <div key={i} className="flex items-center gap-2 bg-gray-50 rounded-lg px-3 py-2 text-xs">
                        <Globe className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                        <span className="text-gray-600 truncate">{p.url}</span>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-4">
            <div className="bg-white border border-gray-200 rounded-xl p-5">
              <h3 className="font-semibold text-gray-900 text-sm mb-4">Crew Summary</h3>
              {Object.entries(issuesByAgent).length === 0 ? (
                <p className="text-gray-400 text-xs">Waiting for agent reports…</p>
              ) : (
                <div className="space-y-3">
                  {Object.entries(issuesByAgent).map(([agent, agentIssues]) => (
                    <div key={agent} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-gray-400 text-sm">{agentGlyph(agent)}</span>
                        <span className="text-gray-600 text-xs">{agentLabel(agent)}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-gray-900 font-bold text-sm">{agentIssues.length}</span>
                        {agentIssues.filter(i => i.severity === 'critical').length > 0 && (
                          <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-medium">
                            {agentIssues.filter(i => i.severity === 'critical').length}C
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {issues.length > 0 && (
              <div className="bg-white border border-gray-200 rounded-xl p-5">
                <h3 className="font-semibold text-gray-900 text-sm mb-4">Severity Breakdown</h3>
                {(['critical', 'high', 'medium', 'low'] as const).map(s => {
                  const count = issues.filter(i => i.severity === s).length;
                  const pct = Math.round((count / issues.length) * 100);
                  return (
                    <div key={s} className="mb-3">
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-gray-500 capitalize">{s}</span>
                        <span className="text-gray-700 font-medium">{count}</span>
                      </div>
                      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${s === 'critical' ? 'bg-red-500' : s === 'high' ? 'bg-orange-500' : s === 'medium' ? 'bg-yellow-500' : 'bg-blue-500'}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <button onClick={() => onNavigate('dashboard')} className="w-full border border-gray-200 hover:border-gray-400 text-gray-500 hover:text-gray-900 py-2.5 rounded-lg text-sm transition">
              Back to Dashboard
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Admin Dashboard ──────────────────────────────────────────────────────────

function AdminPage({ profile }: { profile: UserProfile }) {
  console.log('[AdminPage] render — admin:', profile.email);
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [blockUserId, setBlockUserId] = useState('');
  const [blockReason, setBlockReason] = useState('');
  const [blockDomain, setBlockDomain] = useState('');
  const [blockDomainReason, setBlockDomainReason] = useState('');
  const [message, setMessage] = useState('');
  const [activeTab, setActiveTab] = useState<'users' | 'block'>('users');

  const loadUsers = useCallback(async () => {
    console.log('[AdminPage] loadUsers');
    setLoading(true);
    const { data, error } = await supabase.from('users').select('*').order('created_at', { ascending: false });
    if (!error) setUsers((data ?? []) as UserProfile[]);
    else { console.error('[AdminPage] load users error:', error); setMessage('Failed to load users: ' + error.message); }
    setLoading(false);
  }, []);

  useEffect(() => { loadUsers(); }, [loadUsers]);

  const doBlockUser = async () => {
    if (!blockUserId) return;
    const { error } = await supabase
      .from('users')
      .update({ is_blocked: true, blocked_reason: blockReason || null, blocked_at: new Date().toISOString() })
      .eq('id', blockUserId);
    if (error) { console.error('[AdminPage] block user error:', error); setMessage('Error: ' + error.message); return; }
    await supabase.from('blocked_users').upsert({ user_id: blockUserId, reason: blockReason || null, blocked_by: profile.id });
    setMessage('User blocked.');
    setBlockUserId('');
    setBlockReason('');
    loadUsers();
  };

  const doUnblockUser = async (uid: string) => {
    await supabase.from('users').update({ is_blocked: false, blocked_reason: null, blocked_at: null }).eq('id', uid);
    await supabase.from('blocked_users').delete().eq('user_id', uid);
    setMessage('User unblocked.');
    loadUsers();
  };

  const doBlockDomain = async () => {
    if (!blockDomain) return;
    const domain = blockDomain.replace(/^@/, '').toLowerCase();
    const { error } = await supabase.from('blocked_domains').upsert({ domain, reason: blockDomainReason || null, is_active: true });
    if (error) { console.error('[AdminPage] block domain error:', error); setMessage('Error: ' + error.message); return; }
    setMessage(`Domain @${domain} blocked.`);
    setBlockDomain('');
    setBlockDomainReason('');
  };

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-8">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Admin Dashboard</h1>
            <p className="text-gray-400 text-sm mt-0.5">{profile.email}</p>
          </div>
          <button onClick={loadUsers} className="flex items-center gap-2 text-gray-400 hover:text-gray-900 text-sm transition">
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>

        {message && (
          <div role="status" className="bg-white border border-blue-200 text-gray-700 text-sm rounded-lg px-4 py-3 mb-5 flex justify-between items-center">
            {message}
            <button onClick={() => setMessage('')} aria-label="Dismiss"><X className="w-4 h-4" /></button>
          </div>
        )}

        <div className="flex border-b border-gray-200 mb-6">
          {[
            { key: 'users', label: `Accounts (${users.length})` },
            { key: 'block', label: 'Block Controls' },
          ].map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as 'users' | 'block')}
              className={`px-5 py-3 text-sm font-medium transition ${activeTab === tab.key ? 'border-b-2 border-teal-500 text-teal-600' : 'text-gray-400 hover:text-gray-700'}`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'users' && (
          loading ? (
            <div className="text-center py-16">
              <RefreshCw className="w-6 h-6 text-teal-500 animate-spin mx-auto mb-3" aria-label="Loading" />
              <p className="text-gray-400 text-sm">Loading accounts…</p>
            </div>
          ) : users.length === 0 ? (
            <div className="text-center py-16">
              <Users className="w-10 h-10 text-gray-200 mx-auto mb-3" />
              <p className="text-gray-400">No accounts registered yet.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {users.map(u => (
                <div key={u.id} className={`bg-white border rounded-xl p-5 ${u.is_blocked ? 'border-red-200' : 'border-gray-200'}`}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-gray-900 truncate">{u.email}</span>
                        {u.email === 'shivakumarkannan2006@gmail.com' && (
                          <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">you (admin)</span>
                        )}
                        {u.email_verified
                          ? <span className="text-xs text-green-600 flex items-center gap-1"><CheckCircle className="w-3 h-3" />verified</span>
                          : <span className="text-xs text-gray-400">unverified</span>
                        }
                        {u.is_blocked && (
                          <span className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full font-medium">
                            blocked{u.blocked_reason ? `: ${u.blocked_reason}` : ''}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-4 mt-1.5 text-xs text-gray-400">
                        <span>ID: {u.id.slice(0, 8)}…</span>
                        <span>Joined {new Date(u.created_at).toLocaleDateString()}</span>
                        {u.last_login && <span>Last login {new Date(u.last_login).toLocaleDateString()}</span>}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {u.is_blocked ? (
                        <button
                          onClick={() => doUnblockUser(u.id)}
                          className="flex items-center gap-1 text-xs bg-green-50 hover:bg-green-100 border border-green-200 text-green-700 px-3 py-1.5 rounded-lg transition font-medium"
                        >
                          <CheckCircle className="w-3.5 h-3.5" />
                          Unblock
                        </button>
                      ) : u.role !== 'admin' ? (
                        <button
                          onClick={() => { setBlockUserId(u.id); setActiveTab('block'); }}
                          className="flex items-center gap-1 text-xs bg-red-50 hover:bg-red-100 border border-red-200 text-red-600 px-3 py-1.5 rounded-lg transition font-medium"
                        >
                          <Ban className="w-3.5 h-3.5" />
                          Block
                        </button>
                      ) : null}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )
        )}

        {activeTab === 'block' && (
          <div className="grid sm:grid-cols-2 gap-6">
            <div className="bg-white border border-gray-200 rounded-xl p-6">
              <div className="flex items-center gap-2 mb-4">
                <Trash2 className="w-5 h-5 text-red-500" />
                <h3 className="font-semibold text-gray-900">Block User Account</h3>
              </div>
              <div className="space-y-3">
                <div>
                  <label className="text-gray-500 text-xs font-medium mb-1 block" htmlFor="block-user-id">User ID</label>
                  <input
                    id="block-user-id"
                    type="text"
                    value={blockUserId}
                    onChange={e => setBlockUserId(e.target.value)}
                    placeholder="UUID from accounts list"
                    className="w-full bg-gray-50 border border-gray-200 text-gray-900 px-3 py-2 rounded-lg text-sm font-mono focus:outline-none focus:border-red-400 placeholder-gray-400 transition"
                  />
                </div>
                <div>
                  <label className="text-gray-500 text-xs font-medium mb-1 block" htmlFor="block-reason">Reason (optional)</label>
                  <input
                    id="block-reason"
                    type="text"
                    value={blockReason}
                    onChange={e => setBlockReason(e.target.value)}
                    placeholder="Policy violation, spam…"
                    className="w-full bg-gray-50 border border-gray-200 text-gray-900 px-3 py-2 rounded-lg text-sm focus:outline-none focus:border-red-400 placeholder-gray-400 transition"
                  />
                </div>
                <button
                  onClick={doBlockUser}
                  disabled={!blockUserId}
                  className="w-full bg-red-600 hover:bg-red-700 disabled:opacity-40 text-white text-sm font-semibold py-2 rounded-lg transition"
                >
                  Block Account
                </button>
              </div>
            </div>

            <div className="bg-white border border-gray-200 rounded-xl p-6">
              <div className="flex items-center gap-2 mb-4">
                <Ban className="w-5 h-5 text-orange-500" />
                <h3 className="font-semibold text-gray-900">Block Email Domain</h3>
              </div>
              <div className="space-y-3">
                <div>
                  <label className="text-gray-500 text-xs font-medium mb-1 block" htmlFor="block-domain">Domain</label>
                  <div className="flex">
                    <span className="bg-gray-100 border border-gray-200 border-r-0 text-gray-500 px-3 py-2 rounded-l-lg text-sm select-none">@</span>
                    <input
                      id="block-domain"
                      type="text"
                      value={blockDomain}
                      onChange={e => setBlockDomain(e.target.value)}
                      placeholder="soandso.edu"
                      className="flex-1 bg-gray-50 border border-gray-200 text-gray-900 px-3 py-2 rounded-r-lg text-sm focus:outline-none focus:border-orange-400 placeholder-gray-400 transition"
                    />
                  </div>
                  <p className="text-gray-400 text-xs mt-1">All signups from this domain will be blocked.</p>
                </div>
                <div>
                  <label className="text-gray-500 text-xs font-medium mb-1 block" htmlFor="block-domain-reason">Reason (optional)</label>
                  <input
                    id="block-domain-reason"
                    type="text"
                    value={blockDomainReason}
                    onChange={e => setBlockDomainReason(e.target.value)}
                    placeholder="Disposable email, spam domain…"
                    className="w-full bg-gray-50 border border-gray-200 text-gray-900 px-3 py-2 rounded-lg text-sm focus:outline-none focus:border-orange-400 placeholder-gray-400 transition"
                  />
                </div>
                <button
                  onClick={doBlockDomain}
                  disabled={!blockDomain}
                  className="w-full bg-orange-600 hover:bg-orange-700 disabled:opacity-40 text-white text-sm font-semibold py-2 rounded-lg transition"
                >
                  Block Domain
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── App Root ─────────────────────────────────────────────────────────────────

export default function App() {
  console.log('[App] render');
  const [page, setPage] = useState<Page>('landing');
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [auditUrl, setAuditUrl] = useState('');
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session?.user) {
        loadProfile(session.user).finally(() => setAuthReady(true));
      } else {
        setAuthReady(true);
      }
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      (async () => {
        console.log('[App] onAuthStateChange event:', event);
        if (event === 'SIGNED_OUT' || !session) {
          setProfile(null);
          setPage('landing');
        }
      })();
    });

    return () => subscription.unsubscribe();
  }, []);

  const loadProfile = async (authUser: User) => {
    console.log('[App] loadProfile for', authUser.id);
    const { data, error } = await supabase.from('users').select('*').eq('id', authUser.id).maybeSingle();
    if (error) console.error('[App] loadProfile error:', error);
    if (data) {
      setProfile(data as UserProfile);
      setPage((data as UserProfile).role === 'admin' ? 'admin' : 'dashboard');
    } else {
      console.warn('[App] no profile found for user, creating fallback');
      const newProfile: UserProfile = {
        id: authUser.id,
        email: authUser.email ?? '',
        role: authUser.email === 'shivakumarkannan2006@gmail.com' ? 'admin' : 'user',
        email_verified: !!authUser.email_confirmed_at,
        created_at: new Date().toISOString(),
        is_blocked: false,
      };
      const { error: upsertErr } = await supabase.from('users').upsert(newProfile);
      if (upsertErr) console.error('[App] upsert error:', upsertErr);
      setProfile(newProfile);
      setPage(newProfile.role === 'admin' ? 'admin' : 'dashboard');
    }
  };

  const handleLogin = (p: UserProfile) => {
    console.log('[App] handleLogin — role:', p.role);
    setProfile(p);
    setPage(p.role === 'admin' ? 'admin' : 'dashboard');
  };

  const handleLogout = async () => {
    console.log('[App] handleLogout');
    await supabase.auth.signOut();
    setProfile(null);
    setPage('landing');
  };

  const handleNavigate = (p: Page) => {
    console.log('[App] handleNavigate →', p);
    const protected_pages: Page[] = ['dashboard', 'evaluation', 'audit-results', 'admin'];
    if (protected_pages.includes(p) && !profile) { setPage('login'); return; }
    if (p === 'admin' && profile?.role !== 'admin') { setPage('dashboard'); return; }
    setPage(p);
  };

  const handleStartAudit = (_url: string, _name: string, _siteId: string) => {
    console.log('[App] handleStartAudit — url:', _url, 'siteId:', _siteId);
    setAuditUrl(_url);
    setPage('audit-results');
  };

  if (!authReady) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center" aria-busy="true">
        <div className="flex flex-col items-center gap-3">
          <Shield className="w-10 h-10 text-teal-500 animate-pulse" />
          <p className="text-gray-400 text-sm">Loading…</p>
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary name="App">
      <div className="min-h-screen bg-white">
        <Nav page={page} profile={profile} onNavigate={handleNavigate} onLogout={handleLogout} />

        <ErrorBoundary name="LandingPage">
          {page === 'landing' && <LandingPage onNavigate={handleNavigate} />}
        </ErrorBoundary>

        <ErrorBoundary name="LoginPage">
          {page === 'login' && <LoginPage onNavigate={handleNavigate} onLogin={handleLogin} />}
        </ErrorBoundary>

        <ErrorBoundary name="SignupPage">
          {page === 'signup' && <SignupPage onNavigate={handleNavigate} onLogin={handleLogin} />}
        </ErrorBoundary>

        <ErrorBoundary name="DashboardPage">
          {page === 'dashboard' && profile && <DashboardPage profile={profile} onNavigate={handleNavigate} />}
        </ErrorBoundary>

        <ErrorBoundary name="EvaluationPage">
          {page === 'evaluation' && profile && (
            <EvaluationPage profile={profile} onNavigate={handleNavigate} onStartAudit={handleStartAudit} />
          )}
        </ErrorBoundary>

        <ErrorBoundary name="AuditResultsPage">
          {page === 'audit-results' && (
            <AuditResultsPage auditUrl={auditUrl} onNavigate={handleNavigate} />
          )}
        </ErrorBoundary>

        <ErrorBoundary name="AdminPage">
          {page === 'admin' && profile?.role === 'admin' && (
            <AdminPage profile={profile} />
          )}
        </ErrorBoundary>
      </div>
    </ErrorBoundary>
  );
}
