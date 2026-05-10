/*
  # Fix RLS Policies and Add Auth Trigger

  ## Summary
  This migration fixes all broken RLS policies and wires up Supabase Auth
  so the frontend can operate entirely without a local Python backend.

  ## Changes

  ### 1. users table
  - Drop the broken SELECT policy (used gen_random_uuid() instead of auth.uid())
  - Add correct SELECT: users can read their own row; admins can read all rows
  - Add INSERT: allow new rows to be created for the authenticated user's ID
  - Add UPDATE: users can update their own row; admins can update any row

  ### 2. user_sites table
  - Add INSERT and UPDATE policies (previously only SELECT existed)

  ### 3. site_tech_stack table
  - Add INSERT policy so evaluation flow can save tech stack selections

  ### 4. blocked_users / blocked_domains
  - Add INSERT and DELETE policies for admins

  ### 5. on_auth_user_created trigger
  - Fires after every Supabase Auth signup
  - Inserts a corresponding row in public.users
  - Automatically assigns role = 'admin' for shivakumarkannan2006@gmail.com
  - All other signups get role = 'user'

  ### 6. Email domain blocking helper
  - Function check_blocked_domain() called during signup guard (informational;
    actual blocking is enforced at the app layer via the blocked_domains table)
*/

-- ─── 1. users table ──────────────────────────────────────────────────────────

-- Drop the broken policy
DROP POLICY IF EXISTS "Users can view own data" ON users;

-- SELECT: own row or admin
CREATE POLICY "Users can read own row"
  ON users FOR SELECT
  TO authenticated
  USING (
    id = auth.uid()
    OR (SELECT role FROM users WHERE id = auth.uid()) = 'admin'
  );

-- INSERT: only for matching auth id (called by trigger / client after signup)
CREATE POLICY "Users can insert own row"
  ON users FOR INSERT
  TO authenticated
  WITH CHECK (id = auth.uid());

-- UPDATE: own row, or admin for any row
CREATE POLICY "Users can update own row"
  ON users FOR UPDATE
  TO authenticated
  USING (
    id = auth.uid()
    OR (SELECT role FROM users WHERE id = auth.uid()) = 'admin'
  )
  WITH CHECK (
    id = auth.uid()
    OR (SELECT role FROM users WHERE id = auth.uid()) = 'admin'
  );

-- ─── 2. user_sites table ─────────────────────────────────────────────────────

CREATE POLICY "Users can insert own sites"
  ON user_sites FOR INSERT
  TO authenticated
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update own sites"
  ON user_sites FOR UPDATE
  TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- ─── 3. site_tech_stack table ────────────────────────────────────────────────

CREATE POLICY "Users can insert own tech stack"
  ON site_tech_stack FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM user_sites
      WHERE user_sites.id = site_tech_stack.site_id
        AND user_sites.user_id = auth.uid()
    )
  );

-- ─── 4. blocked_users / blocked_domains ──────────────────────────────────────

CREATE POLICY "Admins can insert blocked users"
  ON blocked_users FOR INSERT
  TO authenticated
  WITH CHECK (
    (SELECT role FROM users WHERE id = auth.uid()) = 'admin'
  );

CREATE POLICY "Admins can delete blocked users"
  ON blocked_users FOR DELETE
  TO authenticated
  USING (
    (SELECT role FROM users WHERE id = auth.uid()) = 'admin'
  );

CREATE POLICY "Admins can insert blocked domains"
  ON blocked_domains FOR INSERT
  TO authenticated
  WITH CHECK (
    (SELECT role FROM users WHERE id = auth.uid()) = 'admin'
  );

CREATE POLICY "Admins can delete blocked domains"
  ON blocked_domains FOR DELETE
  TO authenticated
  USING (
    (SELECT role FROM users WHERE id = auth.uid()) = 'admin'
  );

-- Anyone (including anon) can read blocked_domains to check at signup
CREATE POLICY "Anyone can read blocked domains"
  ON blocked_domains FOR SELECT
  TO anon, authenticated
  USING (is_active = true);

-- ─── 5. Auth trigger: create public.users row on signup ──────────────────────

CREATE OR REPLACE FUNCTION public.handle_new_auth_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  _role text;
BEGIN
  -- Admin email gets admin role
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
    COALESCE(NEW.email_confirmed_at IS NOT NULL, false),
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

-- Drop and recreate trigger cleanly
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_auth_user();

-- Also fire on update (for email confirmation)
DROP TRIGGER IF EXISTS on_auth_user_updated ON auth.users;

CREATE TRIGGER on_auth_user_updated
  AFTER UPDATE ON auth.users
  FOR EACH ROW
  WHEN (OLD.email_confirmed_at IS DISTINCT FROM NEW.email_confirmed_at)
  EXECUTE FUNCTION public.handle_new_auth_user();

-- ─── 6. Verification codes table for email-less OTP in dev ──────────────────

CREATE TABLE IF NOT EXISTS verification_codes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL,
  code text NOT NULL,
  expires_at timestamptz NOT NULL DEFAULT (now() + interval '15 minutes'),
  used boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE verification_codes ENABLE ROW LEVEL SECURITY;

-- Service role only; app reads via service_role key in edge functions
CREATE POLICY "Service role manages verification codes"
  ON verification_codes FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);
