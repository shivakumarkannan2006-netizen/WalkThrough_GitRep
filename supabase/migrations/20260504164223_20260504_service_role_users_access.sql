/*
  # Service role and anon access fixes

  1. Allow service_role full access to users table (needed by the auth
     trigger SECURITY DEFINER function).
  2. Ensure anon role can read active blocked_domains (pre-signup check).
*/

-- Service role full access to users
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'users'
      AND policyname = 'Service role full access to users'
  ) THEN
    CREATE POLICY "Service role full access to users"
      ON users FOR ALL
      TO service_role
      USING (true)
      WITH CHECK (true);
  END IF;
END $$;

-- Anon read for blocked_domains (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'blocked_domains'
      AND policyname = 'Anyone can read blocked domains'
  ) THEN
    CREATE POLICY "Anyone can read blocked domains"
      ON blocked_domains FOR SELECT
      TO anon, authenticated
      USING (is_active = true);
  END IF;
END $$;
