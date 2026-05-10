/*
  # Shield Agent Schema - Fact Checker & Fortress Sentry Tables
  
  Adds tables for:
  - External link verification
  - Testimonial audits
  - Security console leaks
  - EXIF metadata findings
*/

-- ============== EXTERNAL LINKS ==============

CREATE TABLE IF NOT EXISTS audit_external_links (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_session_id uuid NOT NULL REFERENCES audit_sessions(id) ON DELETE CASCADE,
  link_url text NOT NULL,
  http_status_code integer,
  response_time_ms integer,
  reachable boolean,
  verified_timestamp timestamptz,
  found_on_page text
);

ALTER TABLE audit_external_links ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view external links in their company's audits"
  ON audit_external_links FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_sessions
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_sessions.id = audit_external_links.audit_session_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== TESTIMONIAL AUDITS ==============

CREATE TABLE IF NOT EXISTS testimonial_audits (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_session_id uuid NOT NULL REFERENCES audit_sessions(id) ON DELETE CASCADE,
  testimonial_text text NOT NULL,
  page_url text,
  authenticity_score_0_100 integer,
  ai_detection_confidence integer,
  specific_details_present boolean,
  flags jsonb
);

ALTER TABLE testimonial_audits ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view testimonials in their company's audits"
  ON testimonial_audits FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_sessions
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_sessions.id = testimonial_audits.audit_session_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== SECURITY CONSOLE LEAKS ==============

CREATE TABLE IF NOT EXISTS security_console_leaks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_session_id uuid NOT NULL REFERENCES audit_sessions(id) ON DELETE CASCADE,
  page_url text,
  console_message_type text,
  detected_pattern_type text,
  message_text text,
  flagged_content text,
  severity text DEFAULT 'critical'
);

ALTER TABLE security_console_leaks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view security leaks in their company's audits"
  ON security_console_leaks FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_sessions
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_sessions.id = security_console_leaks.audit_session_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== EXIF FINDINGS ==============

CREATE TABLE IF NOT EXISTS security_exif_findings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_session_id uuid NOT NULL REFERENCES audit_sessions(id) ON DELETE CASCADE,
  image_url text,
  exif_field_name text,
  exif_value text,
  privacy_risk_level text CHECK (privacy_risk_level IN ('critical', 'high', 'medium', 'low')),
  found_on_page text
);

ALTER TABLE security_exif_findings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view EXIF findings in their company's audits"
  ON security_exif_findings FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_sessions
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_sessions.id = security_exif_findings.audit_session_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== INDEXES ==============

CREATE INDEX IF NOT EXISTS idx_external_links_session ON audit_external_links(audit_session_id);
CREATE INDEX IF NOT EXISTS idx_testimonial_audits_session ON testimonial_audits(audit_session_id);
CREATE INDEX IF NOT EXISTS idx_security_console_leaks_session ON security_console_leaks(audit_session_id);
CREATE INDEX IF NOT EXISTS idx_security_exif_findings_session ON security_exif_findings(audit_session_id);
