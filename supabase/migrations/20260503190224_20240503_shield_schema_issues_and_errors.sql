/*
  # Shield Agent Schema - Issues & Errors Tables
  
  Adds tables for:
  - Core audit issues and navigator errors
  - Interaction metrics and page analysis
*/

-- ============== AUDIT ISSUES ==============

CREATE TABLE IF NOT EXISTS audit_issues (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_session_id uuid NOT NULL REFERENCES audit_sessions(id) ON DELETE CASCADE,
  agent_name text NOT NULL,
  issue_category text NOT NULL,
  specific_issue_detail text NOT NULL,
  severity text DEFAULT 'medium' CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
  affected_url text,
  affected_element_xpath text,
  screenshot_path text,
  remediation_suggestion text,
  additional_data jsonb,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE audit_issues ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view issues in their company's audits"
  ON audit_issues FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_sessions
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_sessions.id = audit_issues.audit_session_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== NAVIGATOR ERRORS ==============

CREATE TABLE IF NOT EXISTS navigator_errors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_session_id uuid NOT NULL REFERENCES audit_sessions(id) ON DELETE CASCADE,
  error_type text NOT NULL,
  error_message text,
  page_url text,
  timestamp timestamptz DEFAULT now()
);

ALTER TABLE navigator_errors ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view navigator errors in their company's audits"
  ON navigator_errors FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_sessions
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_sessions.id = navigator_errors.audit_session_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== INTERACTION METRICS ==============

CREATE TABLE IF NOT EXISTS interaction_metrics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_page_id uuid NOT NULL REFERENCES audit_pages(id) ON DELETE CASCADE,
  element_selector text NOT NULL,
  interaction_duration_ms integer NOT NULL,
  presence_of_loading_indicator boolean DEFAULT false,
  interaction_type text
);

ALTER TABLE interaction_metrics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view interaction metrics in their company's audits"
  ON interaction_metrics FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_pages
      JOIN audit_sessions ON audit_pages.audit_session_id = audit_sessions.id
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_pages.id = interaction_metrics.audit_page_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== INDEXES ==============

CREATE INDEX IF NOT EXISTS idx_audit_issues_session_agent ON audit_issues(audit_session_id, agent_name);
CREATE INDEX IF NOT EXISTS idx_audit_issues_severity ON audit_issues(severity);
CREATE INDEX IF NOT EXISTS idx_navigator_errors_session ON navigator_errors(audit_session_id);
CREATE INDEX IF NOT EXISTS idx_interaction_metrics_page ON interaction_metrics(audit_page_id);
