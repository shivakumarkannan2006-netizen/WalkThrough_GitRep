/*
  # Shield Agent Schema - Vault Counsel Tables
  
  Adds tables for compliance and integrity checking:
  - Company documents and RAG embeddings
  - Pricing and contact consistency
  - Cookie/GDPR compliance
*/

-- ============== COMPANY DOCUMENTS ==============

CREATE TABLE IF NOT EXISTS company_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  file_name text NOT NULL,
  file_path text NOT NULL,
  upload_date timestamptz DEFAULT now(),
  document_type text CHECK (document_type IN ('legal', 'policy', 'pricing', 'ethics', 'gdpr')),
  file_size_bytes integer
);

ALTER TABLE company_documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view company documents"
  ON company_documents FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM company_users
      WHERE company_users.company_id = company_documents.company_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== DOCUMENT EMBEDDINGS ==============

CREATE TABLE IF NOT EXISTS company_document_embeddings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_document_id uuid NOT NULL REFERENCES company_documents(id) ON DELETE CASCADE,
  chunk_index integer,
  chunk_text text NOT NULL,
  embedding_vector vector(1536),
  chunk_start_offset integer,
  chunk_end_offset integer
);

ALTER TABLE company_document_embeddings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view embeddings for company documents"
  ON company_document_embeddings FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM company_documents
      JOIN company_users ON company_documents.company_id = company_users.company_id
      WHERE company_documents.id = company_document_embeddings.company_document_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== PRICING INCONSISTENCIES ==============

CREATE TABLE IF NOT EXISTS pricing_inconsistencies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_session_id uuid NOT NULL REFERENCES audit_sessions(id) ON DELETE CASCADE,
  location_1_url text NOT NULL,
  location_1_price text NOT NULL,
  location_2_url text NOT NULL,
  location_2_price text NOT NULL,
  currency text,
  price_difference_percentage numeric
);

ALTER TABLE pricing_inconsistencies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view pricing inconsistencies in their company's audits"
  ON pricing_inconsistencies FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_sessions
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_sessions.id = pricing_inconsistencies.audit_session_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== CONTACT INFO MISMATCHES ==============

CREATE TABLE IF NOT EXISTS contact_info_mismatches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_session_id uuid NOT NULL REFERENCES audit_sessions(id) ON DELETE CASCADE,
  page_1_url text NOT NULL,
  page_1_email text,
  page_1_phone text,
  page_2_url text NOT NULL,
  page_2_email text,
  page_2_phone text,
  mismatch_type text
);

ALTER TABLE contact_info_mismatches ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view contact info mismatches in their company's audits"
  ON contact_info_mismatches FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_sessions
      JOIN company_users ON audit_sessions.company_id = audit_sessions.company_id
      WHERE audit_sessions.id = contact_info_mismatches.audit_session_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== COOKIE CONSENT VIOLATIONS ==============

CREATE TABLE IF NOT EXISTS cookie_consent_violations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_session_id uuid NOT NULL REFERENCES audit_sessions(id) ON DELETE CASCADE,
  cookie_name text NOT NULL,
  set_before_consent boolean DEFAULT false,
  consent_type text,
  cookie_value_snippet text
);

ALTER TABLE cookie_consent_violations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view cookie violations in their company's audits"
  ON cookie_consent_violations FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_sessions
      JOIN company_users ON audit_sessions.company_id = audit_sessions.company_id
      WHERE audit_sessions.id = cookie_consent_violations.audit_session_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== GDPR ISSUES ==============

CREATE TABLE IF NOT EXISTS gdpr_issues (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_session_id uuid NOT NULL REFERENCES audit_sessions(id) ON DELETE CASCADE,
  issue_type text NOT NULL,
  affected_page_url text,
  relevant_text text,
  severity text DEFAULT 'high'
);

ALTER TABLE gdpr_issues ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view GDPR issues in their company's audits"
  ON gdpr_issues FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_sessions
      JOIN company_users ON audit_sessions.company_id = audit_sessions.company_id
      WHERE audit_sessions.id = gdpr_issues.audit_session_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== INDEXES ==============

CREATE INDEX IF NOT EXISTS idx_company_documents_company ON company_documents(company_id);
CREATE INDEX IF NOT EXISTS idx_company_document_embeddings_doc ON company_document_embeddings(company_document_id);
CREATE INDEX IF NOT EXISTS idx_pricing_inconsistencies_session ON pricing_inconsistencies(audit_session_id);
CREATE INDEX IF NOT EXISTS idx_contact_info_mismatches_session ON contact_info_mismatches(audit_session_id);
