/*
  # Shield Agent Schema - Mirror Stylist Tables
  
  Adds tables for aesthetic and UX issue detection:
  - Contrast failures
  - Z-index collisions
  - Touch target issues
*/

-- ============== CONTRAST FAILURES ==============

CREATE TABLE IF NOT EXISTS contrast_failures (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_page_id uuid NOT NULL REFERENCES audit_pages(id) ON DELETE CASCADE,
  element_selector text NOT NULL,
  foreground_color text,
  background_color text,
  contrast_ratio numeric(4, 2),
  wcag_level text CHECK (wcag_level IN ('AA', 'AAA', 'FAIL')),
  element_text text
);

ALTER TABLE contrast_failures ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view contrast failures in their company's audits"
  ON contrast_failures FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_pages
      JOIN audit_sessions ON audit_pages.audit_session_id = audit_sessions.id
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_pages.id = contrast_failures.audit_page_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== Z-INDEX COLLISIONS ==============

CREATE TABLE IF NOT EXISTS z_index_collisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_page_id uuid NOT NULL REFERENCES audit_pages(id) ON DELETE CASCADE,
  element_1_selector text NOT NULL,
  element_1_z_index integer,
  element_2_selector text NOT NULL,
  element_2_z_index integer,
  collision_description text
);

ALTER TABLE z_index_collisions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view z-index collisions in their company's audits"
  ON z_index_collisions FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_pages
      JOIN audit_sessions ON audit_pages.audit_session_id = audit_sessions.id
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_pages.id = z_index_collisions.audit_page_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== TOUCH TARGET FAILURES ==============

CREATE TABLE IF NOT EXISTS touch_target_failures (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_page_id uuid NOT NULL REFERENCES audit_pages(id) ON DELETE CASCADE,
  element_selector text NOT NULL,
  width_px integer,
  height_px integer,
  distance_to_nearest_clickable_px integer,
  failure_type text
);

ALTER TABLE touch_target_failures ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view touch target failures in their company's audits"
  ON touch_target_failures FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_pages
      JOIN audit_sessions ON audit_pages.audit_session_id = audit_sessions.id
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_pages.id = touch_target_failures.audit_page_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== INDEXES ==============

CREATE INDEX IF NOT EXISTS idx_contrast_failures_page ON contrast_failures(audit_page_id);
CREATE INDEX IF NOT EXISTS idx_z_index_collisions_page ON z_index_collisions(audit_page_id);
CREATE INDEX IF NOT EXISTS idx_touch_target_failures_page ON touch_target_failures(audit_page_id);
