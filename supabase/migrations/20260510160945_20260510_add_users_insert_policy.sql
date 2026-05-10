/*
  # Add INSERT policy to users table

  The users table had no INSERT policy. The auth trigger (SECURITY DEFINER)
  bypasses RLS so it works fine. But the frontend fallback upsert—used when
  the trigger hasn't fired yet—failed with an RLS violation because authenticated
  users had no INSERT permission.

  This also adds an admin SELECT policy so the admin dashboard can list all users.
*/

-- Allow users to insert their own profile row (for fallback upsert after signup)
CREATE POLICY "Users can insert own profile"
  ON users FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = id);

-- Allow admins to read all users (for admin dashboard)
CREATE POLICY "Admins can read all users"
  ON users FOR SELECT
  TO authenticated
  USING (
    auth.uid() = id
    OR EXISTS (
      SELECT 1 FROM users self WHERE self.id = auth.uid() AND self.role = 'admin'
    )
  );

-- Drop the old non-admin select policy since we replaced it
DROP POLICY IF EXISTS "Users can read own profile" ON users;
