/*
  # Remove password_hash from users table

  The users table was originally designed for a custom auth system with
  a separate Python backend. We now use Supabase Auth exclusively —
  passwords are managed in auth.users, not here.

  The NOT NULL constraint on password_hash blocks the auth trigger from
  creating profile rows (it has no hash to insert), which breaks signup.

  This migration drops the column entirely since it is never written to
  or read from by the frontend.
*/

ALTER TABLE public.users DROP COLUMN IF EXISTS password_hash;
