export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type RequestType = "move_in" | "move_out";
export type Status =
  | "draft"
  | "submitted"
  | "under_review"
  | "needs_info"
  | "approved"
  | "scheduled"
  | "completed"
  | "rejected"
  | "cancelled";
export type RuleStatus = "pass" | "fail" | "warn" | "pending";

export interface RuleResult {
  rule: string;
  status: RuleStatus;
  message: string;
  blocking: boolean;
}

export interface Doc {
  doc_type: string;
  file_name: string;
  name_on_document?: string | null;
  valid_until?: string | null;
  uploaded_at?: string;
}

export interface HistoryEvent {
  at: string;
  actor: "resident" | "admin" | "agent" | "system";
  action: string;
  from_status?: Status | null;
  to_status?: Status | null;
  note?: string | null;
}

export interface ReviewBrief {
  summary: string;
  recommendation: "approve" | "request_info" | "reject";
  reasoning: string;
  risk_flags: string[];
  questions_for_resident: string[];
  generated_by: "agent" | "fallback";
  guardrail_note?: string | null;
  auto_approved: boolean;
}

export interface Checklist {
  status: Status;
  missing_fields: string[];
  documents_uploaded: string[];
  documents_missing: string[];
  issues: string[];
  warnings: string[];
  fees: Record<string, number>;
  admin_question?: string | null;
  gate_pass?: string | null;
}

export interface MoveRequest {
  id: string;
  community_id: string;
  request_type: RequestType;
  status: Status;
  resident_name?: string | null;
  phone?: string | null;
  unit?: string | null;
  resident_type?: "owner" | "tenant" | null;
  move_date?: string | null;
  slot?: string | null;
  household_size?: number | null;
  vehicle_count?: number | null;
  notes?: string | null;
  documents: Doc[];
  history: HistoryEvent[];
  created_at: string;
  review?: ReviewBrief | null;
  info_request?: string | null;
  gate_pass?: string | null;
  checklist: Checklist;
  policy_results: RuleResult[];
  allowed_actions: Status[];
  greeting?: string;
}

export interface Community {
  id: string;
  name: string;
  doc_catalog: Record<string, string>;
  slots: { days: string[]; windows: string[]; blackout_dates: string[]; max_per_window: number };
  autonomy: { auto_approve: string[]; auto_schedule: boolean };
  house_rules: string[];
  request_types: Record<
    RequestType,
    {
      label: string;
      required_fields: string[];
      required_docs: Record<string, string[]>;
      fees: Record<string, number>;
      rules: { rule: string; params: Record<string, unknown>; blocking: boolean }[];
      guidance: string[];
    }
  >;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${res.status})`);
  }
  return res.json();
}

const post = <T>(path: string, body?: unknown) =>
  call<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) });

export const api = {
  health: () => call<{ ok: boolean; llm_configured: boolean }>("/health"),
  communities: () => call<Community[]>("/communities"),
  createRequest: (community_id: string, request_type: RequestType) =>
    post<MoveRequest>("/requests", { community_id, request_type }),
  getRequest: (id: string, role: "resident" | "admin" = "resident") =>
    call<MoveRequest>(`/requests/${id}?role=${role}`),
  updateRequest: (id: string, fields: Partial<MoveRequest>) =>
    call<MoveRequest>(`/requests/${id}`, { method: "PATCH", body: JSON.stringify(fields) }),
  uploadDocument: (id: string, doc: Doc) => post<MoveRequest>(`/requests/${id}/documents`, doc),
  submit: (id: string) => post<MoveRequest>(`/requests/${id}/submit`),
  cancel: (id: string, reason?: string) => post<MoveRequest>(`/requests/${id}/cancel`, { reason }),
  chatHistory: (id: string) => call<ChatMessage[]>(`/requests/${id}/chat`),
  chat: (id: string, message: string) =>
    post<{ reply: string; request: MoveRequest }>(`/requests/${id}/chat`, { message }),
  adminQueue: (community_id?: string) =>
    call<MoveRequest[]>(`/admin/requests${community_id ? `?community_id=${community_id}` : ""}`),
  adminAction: (id: string, action: string, note?: string) =>
    post<MoveRequest>(`/admin/requests/${id}/action`, { action, note }),
  regenerateReview: (id: string) => post<MoveRequest>(`/admin/requests/${id}/review`),
};

// Residents aren't authenticated in the prototype; their request ids are
// remembered in this browser so "My requests" works across visits.
const MINE = "move-agent:my-requests";

export function myRequestIds(): string[] {
  try {
    return JSON.parse(localStorage.getItem(MINE) ?? "[]");
  } catch {
    return [];
  }
}

export function rememberRequest(id: string) {
  try {
    localStorage.setItem(MINE, JSON.stringify([id, ...myRequestIds().filter((x) => x !== id)]));
  } catch {
    /* storage unavailable: list just won't persist */
  }
}
