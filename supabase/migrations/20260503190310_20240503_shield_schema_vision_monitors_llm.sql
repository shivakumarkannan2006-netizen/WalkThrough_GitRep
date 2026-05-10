/*
  # Shield Agent Schema - Vision Architect, Monitors, & LLM Tables
  
  Adds tables for:
  - Enhancement strategies and psychology recommendations
  - Reading level and tone analysis
  - DOM mutations and performance bottlenecks
  - Persona interactions
  - LLM interaction logs and agent prompts
*/

-- ============== ENHANCEMENT STRATEGIES ==============

CREATE TABLE IF NOT EXISTS enhancement_strategies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_session_id uuid NOT NULL REFERENCES audit_sessions(id) ON DELETE CASCADE,
  page_url text,
  suggested_enhancement text NOT NULL,
  psychology_principle text,
  expected_impact_description text,
  priority_rank integer,
  category text
);

ALTER TABLE enhancement_strategies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view enhancements in their company's audits"
  ON enhancement_strategies FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_sessions
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_sessions.id = enhancement_strategies.audit_session_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== READING LEVEL AUDITS ==============

CREATE TABLE IF NOT EXISTS reading_level_audits (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_page_id uuid NOT NULL REFERENCES audit_pages(id) ON DELETE CASCADE,
  text_block_selector text NOT NULL,
  flesch_kincaid_grade_level numeric(4, 2),
  ai_pattern_score_0_100 integer,
  text_snippet text
);

ALTER TABLE reading_level_audits ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view reading levels in their company's audits"
  ON reading_level_audits FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_pages
      JOIN audit_sessions ON audit_pages.audit_session_id = audit_sessions.id
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_pages.id = reading_level_audits.audit_page_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== TONE ANALYSIS ==============

CREATE TABLE IF NOT EXISTS tone_analysis (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_page_id uuid NOT NULL REFERENCES audit_pages(id) ON DELETE CASCADE,
  section_name text,
  detected_tone text,
  consistency_score_0_100 integer,
  tone_shift_severity text
);

ALTER TABLE tone_analysis ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view tone analysis in their company's audits"
  ON tone_analysis FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_pages
      JOIN audit_sessions ON audit_pages.audit_session_id = audit_sessions.id
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_pages.id = tone_analysis.audit_page_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== DOM MUTATIONS ==============

CREATE TABLE IF NOT EXISTS dom_mutations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_page_id uuid NOT NULL REFERENCES audit_pages(id) ON DELETE CASCADE,
  mutation_type text NOT NULL,
  element_selector text,
  visual_change_detected boolean DEFAULT false,
  mutation_timestamp timestamptz DEFAULT now()
);

ALTER TABLE dom_mutations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view DOM mutations in their company's audits"
  ON dom_mutations FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_pages
      JOIN audit_sessions ON audit_pages.audit_session_id = audit_sessions.id
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_pages.id = dom_mutations.audit_page_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== PERFORMANCE BOTTLENECKS ==============

CREATE TABLE IF NOT EXISTS performance_bottlenecks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_session_id uuid NOT NULL REFERENCES audit_sessions(id) ON DELETE CASCADE,
  page_url text,
  load_time_ms integer,
  baseline_load_time_ms integer,
  difference_ms integer
);

ALTER TABLE performance_bottlenecks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view performance bottlenecks in their company's audits"
  ON performance_bottlenecks FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_sessions
      JOIN company_users ON audit_sessions.company_id = audit_sessions.company_id
      WHERE audit_sessions.id = performance_bottlenecks.audit_session_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== PERSONA INTERACTIONS ==============

CREATE TABLE IF NOT EXISTS persona_interactions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_page_id uuid NOT NULL REFERENCES audit_pages(id) ON DELETE CASCADE,
  persona_type text NOT NULL,
  issues_triggered jsonb
);

ALTER TABLE persona_interactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view persona interactions in their company's audits"
  ON persona_interactions FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_pages
      JOIN audit_sessions ON audit_pages.audit_session_id = audit_sessions.id
      JOIN company_users ON audit_sessions.company_id = company_users.company_id
      WHERE audit_pages.id = persona_interactions.audit_page_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== LLM INTERACTIONS ==============

CREATE TABLE IF NOT EXISTS llm_interactions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_session_id uuid NOT NULL REFERENCES audit_sessions(id) ON DELETE CASCADE,
  agent_name text NOT NULL,
  prompt_text text NOT NULL,
  llm_model_used text,
  response_text text,
  tokens_used integer,
  response_latency_ms integer,
  timestamp timestamptz DEFAULT now()
);

ALTER TABLE llm_interactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view LLM interactions in their company's audits"
  ON llm_interactions FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM audit_sessions
      JOIN company_users ON audit_sessions.company_id = audit_sessions.company_id
      WHERE audit_sessions.id = llm_interactions.audit_session_id
      AND company_users.user_id = auth.uid()
    )
  );

-- ============== AGENT PROMPTS ==============

CREATE TABLE IF NOT EXISTS agent_prompts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_name text NOT NULL,
  prompt_version integer DEFAULT 1,
  system_prompt_text text NOT NULL,
  example_issues jsonb,
  severity_rules jsonb,
  created_at timestamptz DEFAULT now(),
  UNIQUE(agent_name, prompt_version)
);

ALTER TABLE agent_prompts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read agent prompts"
  ON agent_prompts FOR SELECT
  USING (true);

-- ============== INDEXES ==============

CREATE INDEX IF NOT EXISTS idx_enhancement_strategies_session ON enhancement_strategies(audit_session_id);
CREATE INDEX IF NOT EXISTS idx_reading_level_audits_page ON reading_level_audits(audit_page_id);
CREATE INDEX IF NOT EXISTS idx_tone_analysis_page ON tone_analysis(audit_page_id);
CREATE INDEX IF NOT EXISTS idx_dom_mutations_page ON dom_mutations(audit_page_id);
CREATE INDEX IF NOT EXISTS idx_performance_bottlenecks_session ON performance_bottlenecks(audit_session_id);
CREATE INDEX IF NOT EXISTS idx_persona_interactions_page ON persona_interactions(audit_page_id);
CREATE INDEX IF NOT EXISTS idx_llm_interactions_session ON llm_interactions(audit_session_id);
