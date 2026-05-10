/*
  # Create App Core Tables: users, user_sites, blocked_users, blocked_domains, site_tech_stack

  These tables power the Shield Agent frontend (auth profiles, site tracking, admin controls).
  They were referenced in later migrations but never created.

  ## New Tables

  ### users
  - Mirror of auth.users with app-level role, block status, and profile data
  - Populated automatically by the on_auth_user_created trigger

  ### user_sites
  - Each audit run for a given user is a row; same domain = multiple rows = tabs

  ### site_tech_stack
  - Selected technology tags per site evaluation

  ### blocked_users
  - Admin-managed list of blocked user IDs

  ### blocked_domains
  - Admin-managed list of blocked email domains

  ## Security
  - RLS enabled on all tables
  - Policies restrict access to the owning user or admin role
  - The auth trigger uses SECURITY DEFINER so it bypasses RLS on insert
*/

-- ─── users ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.users (
  id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email text NOT NULL,
  role text NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user')),
  email_verified boolean NOT NULL DEFAULT false,
  email_verified_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  last_login timestamptz,
  is_blocked boolean NOT NULL DEFAULT false,
  blocked_reason text,
  blocked_at timestamptz
);

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Users can read their own row; admins can read all
CREATE POLICY "Users can read own row"
  ON public.users FOR SELECT
  TO authenticated
  USING (
    auth.uid() = id
    OR EXISTS (SELECT 1 FROM public.users u WHERE u.id = auth.uid() AND u.role = 'admin')
  );

-- Users can insert their own profile (fallback if trigger hasn't fired)
CREATE POLICY "Users can insert own profile"
  ON public.users FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = id);

-- Users can update their own row; admins can update any
CREATE POLICY "Users can update own row"
  ON public.users FOR UPDATE
  TO authenticated
  USING (
    auth.uid() = id
    OR EXISTS (SELECT 1 FROM public.users u WHERE u.id = auth.uid() AND u.role = 'admin')
  )
  WITH CHECK (
    auth.uid() = id
    OR EXISTS (SELECT 1 FROM public.users u WHERE u.id = auth.uid() AND u.role = 'admin')
  );

-- ─── user_sites ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.user_sites (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  site_url text NOT NULL,
  site_name text,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.user_sites ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own sites"
  ON public.user_sites FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "Users can insert own sites"
  ON public.user_sites FOR INSERT
  TO authenticated
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update own sites"
  ON public.user_sites FOR UPDATE
  TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- ─── site_tech_stack ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.site_tech_stack (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id uuid NOT NULL REFERENCES public.user_sites(id) ON DELETE CASCADE,
  tech_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.site_tech_stack ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own tech stack"
  ON public.site_tech_stack FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.user_sites
      WHERE user_sites.id = site_tech_stack.site_id
        AND user_sites.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can insert own tech stack"
  ON public.site_tech_stack FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.user_sites
      WHERE user_sites.id = site_tech_stack.site_id
        AND user_sites.user_id = auth.uid()
    )
  );

-- ─── blocked_users ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.blocked_users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
  reason text,
  blocked_by uuid REFERENCES auth.users(id),
  blocked_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.blocked_users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can read blocked users"
  ON public.blocked_users FOR SELECT
  TO authenticated
  USING (
    EXISTS (SELECT 1 FROM public.users u WHERE u.id = auth.uid() AND u.role = 'admin')
  );

CREATE POLICY "Admins can insert blocked users"
  ON public.blocked_users FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (SELECT 1 FROM public.users u WHERE u.id = auth.uid() AND u.role = 'admin')
  );

CREATE POLICY "Admins can delete blocked users"
  ON public.blocked_users FOR DELETE
  TO authenticated
  USING (
    EXISTS (SELECT 1 FROM public.users u WHERE u.id = auth.uid() AND u.role = 'admin')
  );

-- ─── blocked_domains ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.blocked_domains (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  domain text NOT NULL UNIQUE,
  reason text,
  is_active boolean NOT NULL DEFAULT true,
  blocked_by uuid REFERENCES auth.users(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.blocked_domains ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read active blocked domains"
  ON public.blocked_domains FOR SELECT
  TO anon, authenticated
  USING (is_active = true);

CREATE POLICY "Admins can insert blocked domains"
  ON public.blocked_domains FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (SELECT 1 FROM public.users u WHERE u.id = auth.uid() AND u.role = 'admin')
  );

CREATE POLICY "Admins can update blocked domains"
  ON public.blocked_domains FOR UPDATE
  TO authenticated
  USING (
    EXISTS (SELECT 1 FROM public.users u WHERE u.id = auth.uid() AND u.role = 'admin')
  )
  WITH CHECK (
    EXISTS (SELECT 1 FROM public.users u WHERE u.id = auth.uid() AND u.role = 'admin')
  );

-- ─── Auth trigger: auto-create users row on signup ───────────────────────────

CREATE OR REPLACE FUNCTION public.handle_new_auth_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  _role text;
BEGIN
  IF NEW.email = 'shivakumarkannan2006@gmail.com' THEN
    _role := 'admin';
  ELSE
    _role := 'user';
  END IF;

  INSERT INTO public.users (id, email, role, email_verified, email_verified_at, created_at, updated_at)
  VALUES (
    NEW.id,
    NEW.email,
    _role,
    (NEW.email_confirmed_at IS NOT NULL),
    NEW.email_confirmed_at,
    NOW(),
    NOW()
  )
  ON CONFLICT (id) DO UPDATE SET
    email = EXCLUDED.email,
    email_verified = EXCLUDED.email_verified,
    email_verified_at = EXCLUDED.email_verified_at,
    updated_at = NOW();

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_auth_user();

DROP TRIGGER IF EXISTS on_auth_user_updated ON auth.users;

CREATE TRIGGER on_auth_user_updated
  AFTER UPDATE ON auth.users
  FOR EACH ROW
  WHEN (OLD.email_confirmed_at IS DISTINCT FROM NEW.email_confirmed_at)
  EXECUTE FUNCTION public.handle_new_auth_user();

-- ─── Indexes ──────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_user_sites_user_id ON public.user_sites(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);
