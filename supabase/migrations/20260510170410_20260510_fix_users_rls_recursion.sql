/*
  # Fix infinite recursion in users RLS policies

  The SELECT and UPDATE policies on public.users used a subquery like:
    EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role = 'admin')
  This causes infinite recursion because the policy re-evaluates itself.

  Fix: use auth.jwt() to read the role from the JWT claims instead.
  The trigger stores role in raw_app_meta_data so it's available in the JWT.

  We also drop all duplicate/conflicting policies from previous migrations.
*/

-- Drop all existing policies on users to start clean
DROP POLICY IF EXISTS "Users can read own row" ON public.users;
DROP POLICY IF EXISTS "Users can insert own profile" ON public.users;
DROP POLICY IF EXISTS "Users can insert own row" ON public.users;
DROP POLICY IF EXISTS "Users can update own row" ON public.users;
DROP POLICY IF EXISTS "Admins can read all users" ON public.users;
DROP POLICY IF EXISTS "Users can read own profile" ON public.users;

-- SELECT: own row always readable; admins identified by JWT claim
CREATE POLICY "Users can read own row"
  ON public.users FOR SELECT
  TO authenticated
  USING (
    auth.uid() = id
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin'
  );

-- INSERT: only your own row
CREATE POLICY "Users can insert own profile"
  ON public.users FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = id);

-- UPDATE: own row, or admin via JWT
CREATE POLICY "Users can update own row"
  ON public.users FOR UPDATE
  TO authenticated
  USING (
    auth.uid() = id
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin'
  )
  WITH CHECK (
    auth.uid() = id
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin'
  );
