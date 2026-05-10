/*
  # Shield Agent Database Schema - Core Tables
  
  Enables pgvector extension and creates foundational tables for:
  - Company and user management
  - Core audit sessions and pages
  - AXTree snapshots and interactions
  - Basic page audit data
*/

-- Enable pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- ============== COMPANIES ==============

CREATE TABLE IF NOT EXISTS companies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_name text NOT NULL,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE companies ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS company_users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at timestamptz DEFAULT now(),
  UNIQUE(company_id, user_id)
);

ALTER TABLE company_users ENABLE ROW LEVEL SECURITY;

-- Now add policies for companies
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'companies' AND policyname = 'Users can view their company') THEN
    CREATE POLICY "Users can view their company"
      ON companies FOR SELECT
      TO authenticated
      USING (
        EXISTS (
          SELECT 1 FROM company_users
          WHERE company_users.company_id = companies.id
          AND company_users.user_id = auth.uid()
        )
      );
  END IF;
END $$;

CREATE POLICY "Users can view their own company memberships"
  ON company_users FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

-- ============== AUDIT SESSIONS ==============

CREATE TABLE IF NOT EXISTS audit_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  target_url text NOT NULL,
  status text DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'paused')),
  credentials_used boolean DEFAULT false,
  username text,
  created_at timestamptz DEFAULT now(),
  completed_at timestamptz,
  total_pages_discovered integer DEFAULT 0,
  total_issues_found integer DEFAULT 0,
  authenticated_paths_count integer DEFAULT 0,
  unauthenticated_paths_count integer DEFAULT 0
);

ALTER TABLE audit_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view company audits"
  ON audit_sessions FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM company_users
      WHERE company_users.company_id = audit_sessions.company_id
      AND company_users.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can create audits for their company"
  ON audit_sessions FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM company_users
      WHERE company_users.company_id = audit_sessions.company_id
      AND company_users.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can update audits in their company"
  ON audit_sessions FOR UPDATE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM company_users
      WHERE company_users.company_id = audit_sessions.company_id
      AND company_users.user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM company_users
      WHERE company_users.company_id = audit_sessions.company_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== AUDIT PAGES ==============

CREATE TABLE IF NOT EXISTS audit_pages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_session_id uuid NOT NULL REFERENCES audit_sessions(id) ON DELETE CASCADE,
  url text NOT NULL,
  http_status_code integer,
  load_time_ms integer,
  is_accessible_without_auth boolean DEFAULT true,
  discovered_via_url text,
  visited_timestamp timestamptz DEFAULT now(),
  page_title text,
  meta_description text,
  UNIQUE(audit_session_id, url)
);

ALTER TABLE audit_pages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view pages in their company's audits"
  ON audit_pages FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_sessions
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_sessions.id = audit_pages.audit_session_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== PAGE SNAPSHOTS ==============

CREATE TABLE IF NOT EXISTS audit_page_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_page_id uuid NOT NULL REFERENCES audit_pages(id) ON DELETE CASCADE,
  axe_tree_json jsonb NOT NULL,
  page_title text,
  meta_description text,
  headings_hierarchy jsonb,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE audit_page_snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view snapshots in their company's audits"
  ON audit_page_snapshots FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_pages
      JOIN audit_sessions ON audit_pages.audit_session_id = audit_sessions.id
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_pages.id = audit_page_snapshots.audit_page_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== INTERACTIONS ==============

CREATE TABLE IF NOT EXISTS audit_interactions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_page_id uuid NOT NULL REFERENCES audit_pages(id) ON DELETE CASCADE,
  interaction_type text NOT NULL,
  element_selector text,
  load_time_ms integer,
  has_loading_indicator boolean DEFAULT false,
  timestamp timestamptz DEFAULT now()
);

ALTER TABLE audit_interactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view interactions in their company's audits"
  ON audit_interactions FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_pages
      JOIN audit_sessions ON audit_pages.audit_session_id = audit_sessions.id
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_pages.id = audit_interactions.audit_page_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== PAGE AUDIT DATA ==============

CREATE TABLE IF NOT EXISTS page_audit_data (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_page_id uuid NOT NULL REFERENCES audit_pages(id) ON DELETE CASCADE,
  total_forms integer DEFAULT 0,
  total_links integer DEFAULT 0,
  total_buttons integer DEFAULT 0,
  detected_frameworks jsonb,
  total_images integer DEFAULT 0,
  total_interactive_elements integer DEFAULT 0
);

ALTER TABLE page_audit_data ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view page audit data in their company's audits"
  ON page_audit_data FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_pages
      JOIN audit_sessions ON audit_pages.audit_session_id = audit_sessions.id
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_pages.id = page_audit_data.audit_page_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== INDEXES ==============

CREATE INDEX IF NOT EXISTS idx_audit_sessions_company_created ON audit_sessions(company_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_pages_session ON audit_pages(audit_session_id);
CREATE INDEX IF NOT EXISTS idx_company_users_user ON company_users(user_id);
CREATE INDEX IF NOT EXISTS idx_company_users_company ON company_users(company_id);
