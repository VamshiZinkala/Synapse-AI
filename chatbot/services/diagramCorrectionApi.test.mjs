import assert from "node:assert/strict";
import test from "node:test";

import {
  applyDecisionResult,
  fetchCorrectionHistory,
  requestCorrectionProposal,
  resolveTopologyForReview,
  submitCorrectionDecision,
} from "./diagramCorrectionApi.ts";

const proposalResponse = {
  correction_id: "correction-1",
  status: "proposed",
  source: { source_chunk_id: "chunk-1" },
  original_topology: { nodes: [{ name: "original" }], edges: [] },
  corrected_topology: { nodes: [{ name: "proposed" }], edges: [] },
  summary: "A proposal",
  proposed_changes: [],
  validation: { errors: [], warnings: [] },
};

function response(payload, ok = true, statusText = "") {
  return {
    ok,
    statusText,
    json: async () => payload,
  };
}

test("proposal request sends conversation, stable source chunk, user and optional requirements", async () => {
  let captured;
  const originalTopology = structuredClone(proposalResponse.original_topology);
  Object.freeze(originalTopology.nodes[0]);
  Object.freeze(originalTopology.nodes);
  Object.freeze(originalTopology.edges);
  Object.freeze(originalTopology);
  const result = await requestCorrectionProposal({
    conversationId: "conversation-1",
    sourceChunkId: "chunk-1",
    userId: "user-1",
    requirements: "  Keep all visible components.  ",
  }, async (url, init) => {
    captured = { url, init };
    return response(proposalResponse);
  });
  const originalSnapshot = structuredClone(originalTopology);
  const proposal = { corrected_topology: result.corrected_topology };

  assert.equal(captured.url, "http://localhost:8000/diagram/correct");
  assert.deepEqual(JSON.parse(captured.init.body), {
    conversation_id: "conversation-1",
    source_chunk_id: "chunk-1",
    user_id: "user-1",
    requirements: "Keep all visible components.",
  });
  assert.equal(result.correction_id, "correction-1");
  assert.equal(resolveTopologyForReview(originalTopology, proposal, "original"), originalTopology);
  assert.equal(resolveTopologyForReview(originalTopology, proposal, "proposed"), proposalResponse.corrected_topology);
  assert.deepEqual(originalTopology, originalSnapshot);
});

test("proposal request omits blank optional requirements", async () => {
  let body;
  await requestCorrectionProposal({
    conversationId: "conversation-1",
    sourceChunkId: "chunk-1",
    userId: "user-1",
    requirements: "   ",
  }, async (_url, init) => {
    body = JSON.parse(init.body);
    return response(proposalResponse);
  });

  assert.deepEqual(body, {
    conversation_id: "conversation-1",
    source_chunk_id: "chunk-1",
    user_id: "user-1",
  });
});

test("accept and reject call their Phase 2 endpoints and return updated status", async (t) => {
  for (const decision of ["accept", "reject"]) {
    await t.test(decision, async () => {
      let captured;
      const result = await submitCorrectionDecision(
        "correction / 1",
        "user-1",
        decision,
        async (url, init) => {
          captured = { url, init };
          return response({ correction_id: "correction / 1", status: decision === "accept" ? "accepted" : "rejected" });
        },
      );

      assert.equal(captured.url, `http://localhost:8000/diagram/corrections/correction%20%2F%201/${decision}`);
      assert.equal(captured.init.method, "POST");
      assert.deepEqual(JSON.parse(captured.init.body), { user_id: "user-1" });
      assert.equal(result.status, decision === "accept" ? "accepted" : "rejected");

      const originalTopology = { nodes: [{ name: "Original" }], edges: [] };
      const originalSnapshot = structuredClone(originalTopology);
      const originalProposalState = {
        status: "proposed",
        corrected_topology: { nodes: [{ name: "Corrected" }], edges: [] },
      };
      const updatedState = applyDecisionResult(originalProposalState, result, decision);
      assert.equal(updatedState.status, decision === "accept" ? "accepted" : "rejected");
      assert.deepEqual(originalTopology, originalSnapshot);
    });
  }
});

test("API errors become readable errors for the UI", async () => {
  await assert.rejects(
    requestCorrectionProposal({
      conversationId: "conversation-1",
      sourceChunkId: "chunk-1",
      userId: "user-1",
    }, async () => response({ detail: "Source topology not found" }, false, "Not Found")),
    /Source topology not found/,
  );
});

test("history reload is scoped to conversation and user and preserves all proposal statuses", async () => {
  let captured;
  const history = [
    { ...proposalResponse, status: "proposed" },
    { ...proposalResponse, correction_id: "correction-2", status: "accepted" },
    { ...proposalResponse, correction_id: "correction-3", status: "rejected" },
  ];
  const result = await fetchCorrectionHistory(
    "conversation / 1",
    "user-1",
    async (url, init) => {
      captured = { url: new URL(url), init };
      return response({ corrections: history });
    },
  );

  assert.equal(captured.url.pathname, "/conversation/conversation%20%2F%201/corrections");
  assert.equal(captured.url.searchParams.get("user_id"), "user-1");
  assert.equal(captured.init.cache, "no-store");
  assert.deepEqual(result.map(item => item.status), ["proposed", "accepted", "rejected"]);
});
