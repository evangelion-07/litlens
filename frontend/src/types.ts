export type User = { id: string; username: string; display_name: string };
export type Paper = {
  id: string;
  title: string;
  authors: string[];
  source_type: string;
  processing_status: string;
  processing_message?: string;
  page_count: number;
  chunk_count: number;
  latest_analysis_status?: string;
  abstract?: string;
  doi?: string;
  publication_year?: number;
  landing_page_url?: string;
  pdf_url?: string;
};
export type Source = {
  evidence_id: string;
  paper_id: string;
  paper_title: string;
  page_number: number | null;
  section?: string;
  excerpt: string;
  supporting_quotes?: string[];
};
export type SupportingQuote = { evidence_id: string; quote: string };
export type Claim = {
  text: string;
  evidence_ids: string[];
  supporting_quotes?: SupportingQuote[];
};
export type Report = {
  analysis_mode: string;
  title: string;
  coverage: {
    scope: string;
    pages_analyzed: number;
    total_pages: number;
    analyzed_units: number;
    note: string;
  };
  executive_summary: Claim;
  key_findings: Claim[];
  strengths: Claim[];
  section_summaries: Record<
    string,
    { status: string; summary: string; evidence_ids: string[] }
  >;
  weaknesses: {
    statement: string;
    classification: string;
    priority: string;
    why_it_matters: string;
    recommendation: string;
    evidence_ids: string[];
    supporting_quotes?: SupportingQuote[];
  }[];
  recommendations: {
    change: string;
    why: string;
    how: string;
    expected_benefit: string;
    priority: string;
    basis: string;
    evidence_ids: string[];
    supporting_quotes?: SupportingQuote[];
  }[];
  research_gaps: {
    statement: string;
    research_question: string;
    scope_note: string;
    confidence: string;
    evidence_ids: string[];
    supporting_quotes?: SupportingQuote[];
  }[];
  priority_action_plan: {
    action: string;
    rationale: string;
    priority: string;
    evidence_ids: string[];
    supporting_quotes?: SupportingQuote[];
  }[];
  evidence: Source[];
  caveats: string[];
  retrieval?: { mode: string; indexed_chunks: number; notice?: string };
};
export type Job = {
  analysis_id: string;
  paper_id: string;
  paper_title: string;
  status: string;
  stage: string;
  progress: number;
  error?: string;
  report?: Report | null;
  updated_at: string;
};
export type Answer = {
  answer: string;
  answer_mode: string;
  retrieval_mode: string;
  sufficient_evidence: boolean;
  message?: string;
  citations: Source[];
};
export type Turn = {
  role: "user" | "assistant";
  content: string;
  citations?: Source[];
  answer_mode?: string;
  retrieval_mode?: string;
  message?: string;
};
export type Preferences = {
  provider: "ollama" | "api" | "local";
  ollama_url: string;
  ollama_model: string;
  embedding_model: string;
  embeddings_enabled: boolean;
  api_url: string;
  api_model: string;
  has_api_key: boolean;
  has_openalex_api_key: boolean;
  auto_analyze: boolean;
  allow_external_ai: boolean;
};

export type ModelStatus = {
  available: boolean;
  ready: boolean;
  chat_ready: boolean;
  embeddings_ready: boolean;
  missing_models: string[];
  models: { name: string }[];
  message?: string;
};
