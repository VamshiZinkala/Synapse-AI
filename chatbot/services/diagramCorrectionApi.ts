export type CorrectionDecision = "accept" | "reject";

export type CorrectionProposalRequest = {
  conversationId: string;
  sourceChunkId: string;
  userId: string;
  requirements?: string;
};

export type ReviewView = "original" | "proposed";

export type DecisionProposalState = {
  status: "proposed" | "accepted" | "rejected";
  corrected_topology: unknown;
  version_id?: string | null;
  finalized_at?: string | null;
  ui_message?: string;
  ui_error?: string;
};

type ApiErrorPayload = { detail?: string | { message?: string } };
export type CorrectionDecisionResponse = {
  correction_id: string;
  status: "accepted" | "rejected";
  version_id?: string | null;
  corrected_topology?: unknown;
  finalized_at?: string | null;
};

export type CorrectionProposalResponse = {
  correction_id: string;
  status: "proposed" | "accepted" | "rejected";
  source: { conversation_id: string; source_chunk_id: string; source_file?: string | null };
  original_topology: {
    nodes: Array<{
      name: string;
      type: string;
      metadata?: Record<string, unknown> | null;
      attributes?: Array<{ name: string; data_type?: string | null; is_key: "PK" | "FK" | "none" }>;
      source?: string;
      confidence?: string;
    }>;
    edges: Array<{ source: string; target: string; relationship?: string; cardinality_or_type?: string | null }>;
  };
  corrected_topology: CorrectionProposalResponse["original_topology"];
  proposed_changes: Array<{
    operation: string;
    target: Record<string, string>;
    before: unknown;
    after: unknown;
    reason: string;
    confidence: string;
    uncertainty?: string | null;
  }>;
  summary: string;
  ai_warnings?: string[];
  ai_suggestions?: string[];
  validation: { errors: string[]; warnings: string[] };
  requirements?: string;
};

export async function fetchCorrectionHistory(
  conversationId: string,
  userId: string,
  fetcher: typeof fetch = fetch,
  signal?: AbortSignal,
): Promise<CorrectionProposalResponse[]> {
  if (!conversationId || !userId) {
    throw new Error("A conversation and user are required to load correction history");
  }
  const url = new URL(`http://localhost:8000/conversation/${encodeURIComponent(conversationId)}/corrections`);
  url.searchParams.set("user_id", userId);
  const response = await fetcher(url.toString(), { cache: "no-store", signal });
  const payload = await readApiResponse<{ corrections: CorrectionProposalResponse[] }>(response);
  if (!payload || !Array.isArray(payload.corrections)) {
    throw new Error("Correction history returned an invalid response");
  }
  return payload.corrections;
}

export function resolveTopologyForReview<T>(
  originalTopology: T,
  proposal: { corrected_topology: T } | null | undefined,
  view: ReviewView,
): T {
  return view === "proposed" && proposal ? proposal.corrected_topology : originalTopology;
}

export function applyDecisionResult<T extends DecisionProposalState>(
  proposal: T,
  result: CorrectionDecisionResponse,
  decision: CorrectionDecision,
): T {
  const expectedStatus = decision === "accept" ? "accepted" : "rejected";
  if (result.status !== expectedStatus) {
    throw new Error(`Correction API did not confirm ${expectedStatus}`);
  }
  return {
    ...proposal,
    status: result.status,
    version_id: result.version_id ?? proposal.version_id,
    finalized_at: result.finalized_at ?? proposal.finalized_at,
    corrected_topology: result.corrected_topology ?? proposal.corrected_topology,
    ui_message: decision === "accept"
      ? "Correction accepted and saved as a separate diagram version."
      : "Proposal rejected. The original diagram remains unchanged.",
    ui_error: undefined,
  } as T;
}

async function readApiResponse<T>(response: Response): Promise<T> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    payload = undefined;
  }

  if (!response.ok) {
    const detail = typeof payload === "object" && payload !== null
      ? (payload as ApiErrorPayload).detail
      : undefined;
    const message = typeof detail === "string"
      ? detail
      : detail?.message ?? response.statusText ?? "Diagram correction request failed";
    throw new Error(message);
  }

  if (payload === undefined) {
    throw new Error("Diagram correction returned an invalid response");
  }
  return payload as T;
}

export async function requestCorrectionProposal(
  request: CorrectionProposalRequest,
  fetcher: typeof fetch = fetch,
): Promise<CorrectionProposalResponse> {
  if (!request.conversationId || !request.sourceChunkId || !request.userId) {
    throw new Error("A conversation, topology source, and user are required");
  }

  const requirements = request.requirements?.trim();
  const body = {
    conversation_id: request.conversationId,
    source_chunk_id: request.sourceChunkId,
    user_id: request.userId,
    ...(requirements ? { requirements } : {}),
  };
  const response = await fetcher("http://localhost:8000/diagram/correct", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readApiResponse<CorrectionProposalResponse>(response);
}

export async function submitCorrectionDecision(
  correctionId: string,
  userId: string,
  decision: CorrectionDecision,
  fetcher: typeof fetch = fetch,
): Promise<CorrectionDecisionResponse> {
  if (!correctionId || !userId) {
    throw new Error("A correction proposal and user are required");
  }

  const response = await fetcher(
    `http://localhost:8000/diagram/corrections/${encodeURIComponent(correctionId)}/${decision}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId }),
    },
  );
  const payload = await readApiResponse<CorrectionDecisionResponse>(response);
  const expectedStatus = decision === "accept" ? "accepted" : "rejected";
  if (payload.status !== expectedStatus) {
    throw new Error(`Correction API did not confirm ${expectedStatus}`);
  }
  return payload;
}
