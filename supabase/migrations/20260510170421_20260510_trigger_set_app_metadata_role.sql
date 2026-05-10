/*
  # Set app_metadata role on auth.users so JWT carries the role claim

  The RLS policies now read role from auth.jwt() -> 'app_metadata' ->> 'role'.
  Without this, the JWT won't have the claim and admin checks will fail.

  The trigger runs as SECURITY DEFINER and calls auth.update_user() to set
  raw_app_meta_data so every login JWT includes { "role": "admin"|"user" }.
*/

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

  -- Write profile row
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
    email        = EXCLUDED.email,
    email_verified = EXCLUDED.email_verified,
    email_verified_at = EXCLUDED.email_verified_at,
    updated_at   = NOW();

  -- Stamp role into app_metadata so it appears in the JWT
  UPDATE auth.users
  SET raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb) || jsonb_build_object('role', _role)
  WHERE id = NEW.id;

  RETURN NEW;
END;
$$;
