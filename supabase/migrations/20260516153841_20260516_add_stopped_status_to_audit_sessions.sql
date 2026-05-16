/*
  # Add 'stopped' to audit_sessions status constraint

  1. Modified Tables
    - `audit_sessions`
      - Drops existing status CHECK constraint
      - Re-adds it with 'stopped' as a valid value
      - Valid values: 'running', 'completed', 'failed', 'paused', 'stopped'

  2. Notes
    - The stop-audit endpoint already writes 'stopped' but the old constraint
      silently rejected it, leaving rows in 'running' state permanently.
    - No data loss — purely a constraint change.
*/

ALTER TABLE audit_sessions DROP CONSTRAINT IF EXISTS audit_sessions_status_check;

ALTER TABLE audit_sessions
  ADD CONSTRAINT audit_sessions_status_check
  CHECK (status = ANY (ARRAY[
    'running'::text,
    'completed'::text,
    'failed'::text,
    'paused'::text,
    'stopped'::text
  ]));
