"use client";
import { useEffect, useRef, useState, useMemo } from "react";

import { AiOutlineSend } from "react-icons/ai";
import Header from "../../components/Header";
import Sidebar from "../../components/Sidebar";
import { useConversations } from "@/hooks/useConversations";
import { v4 as uuidv4 } from 'uuid'
import ChatMessages from "@/components/ChatMessages";
import { DocumentUploader } from "@/components/DocumentUploader";
import MessageLoader from "@/components/MessageLoader";
import InteractiveSchemaCanvas from "@/components/InteractiveSchemaCanvas";
import {
  applyDecisionResult,
  fetchCorrectionHistory,
  requestCorrectionProposal,
  resolveTopologyForReview,
  submitCorrectionDecision,
} from "@/services/diagramCorrectionApi";

type AttachmentState = {
  id: string;
  file: File;
  status: 'uploading' | 'success' | 'error';
  errorMsg?: string;
};

type DiagramAttribute = {
  name: string;
  data_type?: string | null;
  is_key: "PK" | "FK" | "none";
};

type DiagramNode = {
  name: string;
  type: string;
  metadata?: Record<string, unknown> | null;
  attributes?: DiagramAttribute[] | null;
  source?: string;
  confidence?: string;
};

type DiagramEdge = {
  source: string;
  target: string;
  relationship?: string;
  cardinality_or_type?: string | null;
};

type DiagramTopology = { nodes: DiagramNode[]; edges: DiagramEdge[] };

type TopologyRecord = {
  source_chunk_id: string;
  source_file: string | null;
  topology: DiagramTopology;
};

type CorrectionProposalState = {
  correction_id: string;
  status: "proposed" | "accepted" | "rejected";
  source: {
    conversation_id: string;
    source_chunk_id: string;
    source_file?: string | null;
  };
  original_topology: DiagramTopology;
  corrected_topology: DiagramTopology;
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
  version_id?: string | null;
  finalized_at?: string | null;
  ui_error?: string;
  ui_message?: string;
};

const getConversationTitle = (content: string) => {
  const normalizedContent = content.replace(/\s+/g, " ").trim();
  if (!normalizedContent) return "New Chat";
  return normalizedContent.length > 34 ? `${normalizedContent.slice(0, 34)}...` : normalizedContent;
};


const user_id = 'test_user_id'

function isTopologyRecord(value: unknown): value is TopologyRecord {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Partial<TopologyRecord>;
  return typeof record.source_chunk_id === "string" &&
    (typeof record.source_file === "string" || record.source_file === null) &&
    typeof record.topology === "object" && record.topology !== null &&
    Array.isArray(record.topology.nodes) && Array.isArray(record.topology.edges);
}

async function fetchTopologyRecords(conversationId: string, signal?: AbortSignal): Promise<TopologyRecord[]> {
  const response = await fetch(
    `http://localhost:8000/conversation/${conversationId}/topologies`,
    { signal, cache: "no-store" },
  );
  if (!response.ok) throw new Error(`Could not load diagram sources (${response.status})`);
  const data: unknown = await response.json();
  const records = typeof data === "object" && data !== null
    ? (data as { topology_records?: unknown }).topology_records
    : undefined;
  return Array.isArray(records)
    ? records.filter(isTopologyRecord)
    : [];
}

export default function ChatPage() {
  const { conversations, activeConversationId, setActiveConversationId, setConversations, isConvLoaded, isMessagesLoaded } = useConversations();
  const [attachments, setAttachments] = useState<AttachmentState[]>([]);
  const [input, setInput] = useState<string>("");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const chatContainerRef = useRef<HTMLDivElement>(null); // Purpose: scroll to last index on sent message
  const [isResponseLoading, setIsResponseLoading] = useState<boolean>(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null); // for input text wrapping
  const abortControllerRef = useRef<AbortController | null>(null)
  const isSendingRef = useRef<boolean>(false); // Purpose: only scroll when human input is sent

  const [canvasWidth, setCanvasWidth] = useState(38); // percent (resizable screen)
  const isResizingRef = useRef<boolean>(false);
  const resizeStartX = useRef(0);
  const resizeStartWidth = useRef(38);
  const [activeFiles, setActiveFiles] = useState<string[]>([]);
  // const [activeGraphData, setActiveGraphData] = useState<any>(null);

  const [topologyRecords, setTopologyRecords] = useState<TopologyRecord[]>([]);
  const [activeSourceChunkId, setActiveSourceChunkId] = useState<string | null>(null);
  const [streamTopology, setStreamTopology] = useState<{ source_file: string; topology: DiagramTopology } | null>(null);
  const [correctionProposals, setCorrectionProposals] = useState<CorrectionProposalState[]>([]);
  const [selectedProposalBySource, setSelectedProposalBySource] = useState<Record<string, string>>({});
  const [canvasView, setCanvasView] = useState<"original" | "proposed">("original");
  const [correctionRequirements, setCorrectionRequirements] = useState("");
  const [topologiesLoading, setTopologiesLoading] = useState(false);
  const [topologyLoadError, setTopologyLoadError] = useState<string | null>(null);
  const [correctionError, setCorrectionError] = useState<string | null>(null);
  const [isCorrecting, setIsCorrecting] = useState(false);
  const [decisionLoadingId, setDecisionLoadingId] = useState<string | null>(null);
  const [visualActions, setVisualActions] = useState<any[]>([])

  const [visualEdges, setVisualEdges] = useState<any[]>([]);
  const activeConversation = useMemo(() => {
    return conversations.find((conversation) => conversation.id === activeConversationId) ?? conversations[0]
  }, [activeConversationId, conversations])
  const activeConversationIdRef = useRef(activeConversationId);
  const activeSourceChunkIdRef = useRef<string | null>(null);
  activeConversationIdRef.current = activeConversationId;

  const hasMessages = activeConversation.messages.length > 0;

  const processedToolBlocksRef = useRef(new Set<string>());

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizingRef.current) return;


      const deltaX = resizeStartX.current - e.clientX;

      const deltaPercent = (deltaX / window.innerWidth) * 100;


      const newWidth = resizeStartWidth.current + deltaPercent;

      setCanvasWidth(
        Math.min(70, Math.max(20, newWidth))
      );
    };

    const handleMouseUp = () => {
      isResizingRef.current = false;
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);
  useEffect(() => {// chat input resize
    const textarea = textareaRef.current;

    if (!textarea) return;

    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
  }, [input]);

  useEffect(() => {
    console.log("VISUAL ACTIONS", visualActions);
  }, [visualActions]);

  useEffect(() => {
    console.log("VISUAL EDGES", visualEdges);
  }, [visualEdges]);
  useEffect(() => {
    const isUnsavedDraft = activeConversation.title === "New Chat" && activeConversation.messages.length === 0;
    if (!activeConversationId || isUnsavedDraft) {
      setTopologyRecords([]);
      setActiveSourceChunkId(null);
      setStreamTopology(null);
      setVisualActions([]);
      setVisualEdges([]);
      setCorrectionProposals([]);
      setSelectedProposalBySource({});
      setTopologiesLoading(false);
      setTopologyLoadError(null);
      setCorrectionError(null);
      return;
    }

    const controller = new AbortController();
    setTopologiesLoading(true);
    setTopologyLoadError(null);
    setCorrectionError(null);
    setTopologyRecords([]);
    setActiveSourceChunkId(null);
    setCorrectionProposals([]);
    setSelectedProposalBySource({});
    setStreamTopology(null);
    setVisualActions([]);
    setVisualEdges([]);

    fetchTopologyRecords(activeConversationId, controller.signal)
      .then(records => {
        setTopologyRecords(records);
        setActiveSourceChunkId(records.at(-1)?.source_chunk_id ?? null);
      })
      .catch(error => {
        if (error instanceof Error && error.name === "AbortError") return;
        setTopologyLoadError(error instanceof Error ? error.message : "Could not load diagram sources");
      })
      .finally(() => {
        if (!controller.signal.aborted) setTopologiesLoading(false);
      });

    fetchCorrectionHistory(activeConversationId, user_id, fetch, controller.signal)
      .then(history => {
        if (!controller.signal.aborted) setCorrectionProposals(history);
      })
      .catch(error => {
        if (error instanceof Error && error.name === "AbortError") return;
        if (!controller.signal.aborted) {
          setCorrectionError(error instanceof Error ? error.message : "Could not load correction history");
        }
      });

    return () => controller.abort();
  }, [activeConversationId, activeConversation.title, activeConversation.messages.length])

  useEffect(() => {
    if (!streamTopology || topologyRecords.length === 0) return;
    const matches = topologyRecords.filter(record =>
      record.source_file === streamTopology.source_file &&
      JSON.stringify(record.topology) === JSON.stringify(streamTopology.topology)
    );
    if (matches.length === 1) {
      setActiveSourceChunkId(matches[0].source_chunk_id);
      setStreamTopology(null);
    }
  }, [streamTopology, topologyRecords]);

  useEffect(() => {// messages scroll to end
    if (isSendingRef.current) return;
    const container = chatContainerRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [activeConversation.messages.length])

  const upsertConversation = async (id: string, title: string, userId: string) => {
    const response = await fetch("http://localhost:8000/conversation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, title, user_id: userId })
    });
    if (!response.ok) throw new Error("Failed to initialize conversation in database.");
    return await response.json();
  };

  const handleFilesSelected = async (files: File[]) => {
    if (!activeConversationId) {
      alert("Please start a conversation thread first.")
      return;
    }

    const isUntitledChat = activeConversation.messages.length === 0 && activeConversation.title === 'New Chat';
    if (isUntitledChat) {

      await upsertConversation(activeConversationId, `Document Uploads_${files[0].name}...`, user_id)


      setConversations((currentConversations) =>
        currentConversations.map(conversation =>
          conversation.id === activeConversationId
            ? { ...conversation, title: `Document Uploads_${files[0].name}...` }
            : conversation
        )
      );
    }
    // UI state blocks for all incoming files
    const newAttachments: AttachmentState[] = files.map(file => ({
      id: uuidv4(),
      file,
      status: 'uploading'
    }));

    setAttachments(prev => [...prev, ...newAttachments])

    const uploadPromises = newAttachments.map(async (att) => {
      const formData = new FormData();
      formData.append("file", att.file)
      formData.append("user_id", user_id);
      formData.append("thread_id", activeConversationId)

      const isImage = att.file.type.startsWith('image/');
      const targetEndpoint = isImage ? "http://localhost:8000/upload/uploadimage" : "http://localhost:8000/upload/uploadfile";
      try {
        const response = await fetch(targetEndpoint, {
          method: 'POST',
          body: formData
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || "Upload failed");
        }

        setActiveFiles(prev => [...prev, att.file.name])
        setAttachments(prev => prev.map(p => p.id === att.id ? { ...p, status: 'success' } : p))
      } catch (error: any) {
        console.error(error);
        // update this file status
        setAttachments(prev => prev.map(p =>
          p.id === att.id ? { ...p, status: 'error', errorMsg: error instanceof Error ? error.message : "Failed" } : p
        ));
      }
    })

    await Promise.all(uploadPromises); // for simultaneous execution

    // A new conversation's topology list may have loaded before its first upload.
    // Refresh after uploads so correction uses the returned source_chunk_id.
    try {
      const records = await fetchTopologyRecords(activeConversationId);
      setTopologyRecords(records);
      setActiveSourceChunkId(records.at(-1)?.source_chunk_id ?? null);
      setStreamTopology(null);
      setTopologyLoadError(null);
    } catch (error) {
      setTopologyLoadError(error instanceof Error ? error.message : "Could not refresh diagram sources");
    }
  }


  const handleSendMessage = async () => {
    processedToolBlocksRef.current.clear(); // clearing the tool boxes

    const trimmedInput = input.trim();
    if (!trimmedInput) return;

    setInput("")
    setAttachments([])
    setIsResponseLoading(true)
    let thread_id = activeConversationId;
    try {
      const isUntitledChat = activeConversation.messages.length === 0 && activeConversation.title === 'New Chat';
      let newTitle = activeConversation.title;
      if (isUntitledChat) {
        newTitle = getConversationTitle(trimmedInput)
        await upsertConversation(activeConversationId, newTitle, user_id)
      }

      const humanMsgId = uuidv4()
      const aiMsgId = uuidv4()
      setConversations((currentConversations) =>
        currentConversations.map(conversation => {
          if (conversation.id !== activeConversationId) {
            return conversation;
          }
          return {
            ...conversation,
            title: newTitle,
            id: thread_id,
            messages: [
              ...conversation.messages,
              { id: humanMsgId, role: "human", content: trimmedInput },
              { id: aiMsgId, role: 'ai', content: "", tool_messages: [] },
            ]
          }
        })
      ) // conversations 
      isSendingRef.current = true;
      abortControllerRef.current = new AbortController();
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: abortControllerRef.current.signal,
        body: JSON.stringify({ message: trimmedInput, thread_id: thread_id, human_msg_id: humanMsgId, ai_msg_id: aiMsgId, user_id: user_id, active_files: activeFiles })
      });

      if (!response.ok) {
        throw new Error(`Server Error (${response.status}): The AI provider is likely overloaded. Please try again in a moment.`)
      }

      if (!response.body) throw new Error("No readable stream");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let streamedContent = "";
      let lastUpdate = Date.now();

      let cleanTextAnswer = "" // for clean markdown text bubble
      let toolPayload: any = undefined;
      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          const chunk = decoder.decode(value, { stream: true });

          streamedContent += chunk;
          const now = Date.now()

          // tool data

          const regex = /__TOOL_START__([\s\S]*?)__TOOL_END__/g;
          let match;
          while ((match = regex.exec(streamedContent)) !== null) {
            const toolJson = match[1].trim();

            if (processedToolBlocksRef.current.has(toolJson)) {
              continue;
            }
            processedToolBlocksRef.current.add(toolJson);

            try {
              toolPayload = JSON.parse(toolJson) // tool data extraction

              setConversations(current =>
                current.map(conv => {
                  if (conv.id !== activeConversationId) {
                    return conv;
                  }

                  return {
                    ...conv,
                    messages: conv.messages.map(msg => {
                      if (msg.id !== aiMsgId) {
                        return msg;
                      }

                      const existingIndex =
                        msg.tool_messages?.findIndex(
                          (t: any) =>
                            t.tool_id === toolPayload.tool_id
                        ) ?? -1;

                      let updatedTools = [
                        ...(msg.tool_messages ?? [])
                      ];

                      if (existingIndex >= 0) {
                        updatedTools[existingIndex] = {
                          ...updatedTools[existingIndex],
                          ...toolPayload
                        };
                      } else {
                        updatedTools.push(toolPayload);
                      }

                      return {
                        ...msg,
                        tool_messages: updatedTools
                      };
                    })
                  };
                })
              );

            } catch (err) {
              console.error("failed parsing tool payload", err)
            }
          }

          // graph data
          if (streamedContent.includes("__GRAPH_METADATA_START__")) {
            const parts = streamedContent.split("__GRAPH_METADATA_START__");


            cleanTextAnswer = parts[0]
              .replace(
                /__TOOL_START__[\s\S]*?__TOOL_END__/g,
                ""
              )
              .trim(); // slice before the seperator (message text)

            const remainingBlock = parts[1]
            if (remainingBlock && remainingBlock.includes("__GRAPH_METADATA_END_")) {
              const jsonTargetStr = remainingBlock.split("__GRAPH_METADATA_END__")[0].trim();

              try {
                const completeGraphPayload = JSON.parse(jsonTargetStr)


                if (completeGraphPayload.topology) {
                  const matchingRecord = topologyRecords.find(record =>
                    record.source_file === completeGraphPayload.source_file &&
                    JSON.stringify(record.topology) === JSON.stringify(completeGraphPayload.topology)
                  );
                  if (matchingRecord) {
                    setActiveSourceChunkId(matchingRecord.source_chunk_id);
                    setStreamTopology(null);
                  } else {
                    // Chat can return a retrieved graph before its indexed source list
                    // loads. Keep it visible, but never use its filename as correction identity.
                    setActiveSourceChunkId(null);
                    setStreamTopology({
                      source_file: completeGraphPayload.source_file || "Retrieved diagram",
                      topology: completeGraphPayload.topology,
                    });
                  }
                }
                if (completeGraphPayload.actions) {
                  setVisualActions(completeGraphPayload.actions)
                }

                if (completeGraphPayload.edges) {
                  setVisualEdges(completeGraphPayload.edges)
                }

              } catch (e) {
                console.error("failed parsing metadata payload frame", e)
              }
            }
          } else {
            cleanTextAnswer = streamedContent.replace(/__TOOL_START__[\s\S]*?__TOOL_END__/g, "")
          }

          //update only every 50ms
          if (chunk.includes('\n') || now - lastUpdate > 50 || doneReading) {
            const contentToRender = streamedContent;


            setConversations(currentConversations =>
              currentConversations.map(conversation => {
                if (conversation.id !== activeConversationId) {
                  return conversation
                }
                return {
                  ...conversation,
                  messages: conversation.messages.map((msg, idx) => {
                    if (msg.id === aiMsgId) {
                      console.log("Visible Text", cleanTextAnswer)
                      return {
                        ...msg,
                        content: cleanTextAnswer
                      }
                    }
                    return msg;
                  })
                }
              })
            )
            lastUpdate = now;
          } // end if

        }
      }

    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log("Stream stopped by user.");
      } else {
        console.log(err)
      }
    } finally {
      setIsResponseLoading(false)
      isSendingRef.current = false
    }
  }

  const handleNewChat = () => {
    const emptyConversation = conversations.find(
      (conversation) => conversation.messages.length === 0 && conversation.title === 'New Chat');
    if (emptyConversation) {
      setActiveConversationId(emptyConversation.id);
      setInput("");
      setIsSidebarOpen(false);
      return;
    }

    const newConversation = {
      id: uuidv4(),
      title: "New Chat",
      messages: [],
    };

    setConversations((currentConversations) => [
      newConversation,
      ...currentConversations,
    ]);
    setActiveConversationId(newConversation.id);
    setInput("");
    setIsSidebarOpen(false);
  };

  const handleSelectConversation = (conversationId: string) => {
    setActiveConversationId(conversationId);
    setInput("");
    setIsSidebarOpen(false);
  };

  const sidebarConversations = useMemo(() => {
    return conversations.map(({ id, title }) => ({
      id,
      title,
    }));
  }, [conversations]);

  const activeSourceRecord = topologyRecords.find(
    (record) => record.source_chunk_id === activeSourceChunkId,
  ) ?? null;
  activeSourceChunkIdRef.current = activeSourceChunkId;
  const activeTopology = streamTopology?.topology ?? activeSourceRecord?.topology ?? null;
  const activeSourceFile = streamTopology?.source_file ?? activeSourceRecord?.source_file ?? null;
  const sourceProposals = activeSourceChunkId
    ? correctionProposals.filter((proposal) => proposal.source.source_chunk_id === activeSourceChunkId)
    : [];
  const activeProposalId = activeSourceChunkId
    ? selectedProposalBySource[activeSourceChunkId] ?? sourceProposals[0]?.correction_id
    : undefined;
  const activeProposal = sourceProposals.find(
    (proposal) => proposal.correction_id === activeProposalId,
  ) ?? null;
  const displayedTopology = resolveTopologyForReview(activeTopology, activeProposal, canvasView);

  const handleSelectSource = (sourceChunkId: string) => {
    setActiveSourceChunkId(sourceChunkId || null);
    setStreamTopology(null);
    setCanvasView("original");
    setCorrectionError(null);
    setVisualActions([]);
    setVisualEdges([]);
  };

  const handleCorrectDiagram = async () => {
    if (!activeSourceRecord || !activeConversationId) {
      setCorrectionError("Choose an indexed diagram source before requesting a correction.");
      return;
    }

    const requestConversationId = activeConversationId;
    const requestSourceChunkId = activeSourceRecord.source_chunk_id;
    setCorrectionError(null);
    setIsCorrecting(true);
    try {
      const data = await requestCorrectionProposal({
        conversationId: requestConversationId,
        sourceChunkId: requestSourceChunkId,
        userId: user_id,
        requirements: correctionRequirements,
      });
      if (!data.correction_id || !data.corrected_topology || !data.validation) {
        throw new Error("Correction API returned an incomplete proposal");
      }

      const proposal: CorrectionProposalState = {
        ...data,
        source: {
          ...data.source,
          source_chunk_id: activeSourceRecord.source_chunk_id,
          source_file: activeSourceRecord.source_file,
        },
        ui_message: "Proposal created. The original diagram is unchanged.",
      };
      setCorrectionProposals((current) => [proposal, ...current]);
      setSelectedProposalBySource((current) => ({
        ...current,
        [requestSourceChunkId]: proposal.correction_id,
      }));
      if (
        activeConversationIdRef.current === requestConversationId &&
        activeSourceChunkIdRef.current === requestSourceChunkId
      ) {
        setCanvasView("proposed");
      }
    } catch (error) {
      if (
        activeConversationIdRef.current === requestConversationId &&
        activeSourceChunkIdRef.current === requestSourceChunkId
      ) {
        const message = error instanceof Error ? error.message : "Diagram correction failed";
        setCorrectionError(message.includes("Conversation not found for this user")
          ? "This chat is not saved under the current user. Start a new chat, upload the diagram there, and try again."
          : message);
      }
    } finally {
      setIsCorrecting(false);
    }
  };

  const handleCorrectionDecision = async (decision: "accept" | "reject") => {
    if (!activeProposal) return;
    const correctionId = activeProposal.correction_id;
    setDecisionLoadingId(correctionId);
    setCorrectionProposals((current) => current.map((proposal) =>
      proposal.correction_id === correctionId
        ? { ...proposal, ui_error: undefined, ui_message: undefined }
        : proposal
    ));

    try {
      const result = await submitCorrectionDecision(correctionId, user_id, decision);
      setCorrectionProposals((current) => current.map((proposal) =>
        proposal.correction_id === correctionId
          ? applyDecisionResult(proposal, result, decision)
          : proposal
      ));
      if (
        decision === "reject" &&
        activeSourceChunkIdRef.current === activeProposal.source.source_chunk_id
      ) {
        setCanvasView("original");
      }
    } catch (error) {
      setCorrectionProposals((current) => current.map((proposal) =>
        proposal.correction_id === correctionId
          ? { ...proposal, ui_error: error instanceof Error ? error.message : "Could not update correction" }
          : proposal
      ));
    } finally {
      setDecisionLoadingId(null);
    }
  };
  return (
    <div className="relative flex h-screen overflow-hidden bg-[#090a0f] text-white">
      {/* Linear gradients */}
      <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(8,47,73,0.35),rgba(9,10,15,0.2)_35%,rgba(20,83,45,0.18)_100%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(255,255,255,0.12),transparent_45%)]" />
      {/* <div className="bg-linear-to-r/oklch from-green-500 via-emerald-500 to-teal-500"/> */}
      <div className="relative z-10 flex min-h-0 flex-1">
        <Sidebar
          activeConversationId={activeConversationId}
          conversations={sidebarConversations}
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
          onNewChat={handleNewChat}
          onSelectConversation={handleSelectConversation}
          isConvLoaded={isConvLoaded}
        />

        <section className="flex h-screen w-full overflow-hidden">
          <div className="flex flex-col flex-1 min-w-0">
            <Header
              title={activeConversation?.title ?? "Thread"}
              onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
            />
            <main className="relative mx-auto flex min-h-0 w-full max-w-4xl flex-1 flex-col px-4 md:px-8">
              {
                hasMessages ? (
                  <div className={`flex-1 space-y-5 overflow-y-auto overflow-x-hidden py-6 pb-32 pr-1 [scrollbar-width:thin] [scrollbar-color:rgba(103,232,249,0.45)_transparent]`} ref={chatContainerRef}>
                    <ChatMessages messages={activeConversation.messages} isMessagesLoaded={isMessagesLoaded} />
                  </div>
                ) : (
                  <div className="flex-1" ref={chatContainerRef} />
                )
              }


              <div
                className={`${hasMessages
                  ? "absolute inset-x-4 bottom-6 md:inset-x-8"
                  : "absolute left-1/2 top-1/2 w-[calc(100%-2rem)] max-w-2xl -translate-x-1/2 -translate-y-1/2 md:w-[calc(100%-4rem)]"
                  }`}
              >
                {!hasMessages && (
                  <p className="mb-4 text-center text-sm font-medium uppercase tracking-[0.22em] text-cyan-100/60">
                    Start conversation
                  </p>
                )}

                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (!isResponseLoading && !attachments.some(a => a.status === 'uploading')) {
                      handleSendMessage();
                    }
                  }}
                  className={`flex w-full flex-col gap-2 rounded-[1.75rem] border border-white/12 bg-white/[0.08] p-2.5 shadow-2xl shadow-black/30 backdrop-blur-2xl transition-all duration-300 ${input ? "scale-100 border-cyan-200/25" : "scale-[0.98]"
                    }`}
                >

                  {/* HORIZONTAL SLIDING */}
                  {attachments.length > 0 && (
                    <div className="flex w-full gap-2 overflow-x-auto px-3 pt-1 pb-2 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
                      {attachments.map((att) => (
                        <div
                          key={att.id}
                          className={`flex shrink-0 items-center gap-2 rounded-xl border px-3 py-2 text-xs transition-colors ${att.status === 'error' ? 'border-red-500/50 bg-red-950/40 text-red-200' :
                            att.status === 'success' ? 'border-cyan-700/50 bg-cyan-950/40 text-cyan-100' :
                              'border-white/10 bg-white/5 text-zinc-300'
                            }`}
                        >
                          {att.status === 'uploading' && (
                            <div className="size-3.5 animate-spin rounded-full border-2 border-zinc-400 border-t-cyan-400" />
                          )}
                          {att.status === 'success' && (
                            <svg className="size-3.5 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                          {att.status === 'error' && (
                            <svg className="size-3.5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          )}

                          <span className="max-w-[120px] truncate font-medium">
                            {att.file.name}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="flex w-full items-end gap-2">
                    <DocumentUploader
                      disabled={!activeConversationId || isResponseLoading}
                      onFilesSelected={handleFilesSelected}
                    />
                    <textarea
                      ref={textareaRef}
                      rows={1}
                      placeholder="Ask anything or drop files..."
                      value={input}
                      onChange={(event) => setInput(event.currentTarget.value)}
                      onKeyDown={(event) => {
                        if (!isResponseLoading && event.key === "Enter" && !event.shiftKey) {
                          event.preventDefault();
                          if (!attachments.some(a => a.status === 'uploading')) {
                            handleSendMessage();
                          }
                        }
                      }}
                      // disabled={isResponseLoading}
                      className="min-h-11 min-w-0 flex-1 resize-none break-words bg-transparent px-4 py-3 text-lg leading-6 text-white outline-none placeholder:text-zinc-400 md:text-base [overflow-wrap:anywhere] [scrollbar-width:thin] [scrollbar-color:rgba(103,232,249,0.45)_transparent]"
                    />
                    {isResponseLoading ? (
                      <button
                        type="button"
                        onClick={() => {
                          if (abortControllerRef.current) {
                            abortControllerRef.current.abort();
                          }
                        }}
                        aria-label="Stop generation"
                        className="mb-0.5 grid size-11 shrink-0 place-items-center rounded-full bg-cyan-200 text-slate-950 shadow-lg shadow-red-950/30 transition duration-200 hover:bg-cyan-300 hover:cursor-pointer"
                      >
                        {/* A simple square icon for stop */}
                        <div className="size-4 rounded-[2px] bg-slate-950" />
                      </button>
                    ) : (
                      <button
                        type="submit"
                        disabled={!input.trim() || attachments.some(a => a.status === 'uploading')}
                        aria-label="Send message"
                        className="mb-0.5 grid size-11 shrink-0 place-items-center rounded-full bg-cyan-300 text-slate-950 shadow-lg shadow-cyan-950/30 transition duration-200 hover:bg-cyan-200 disabled:cursor-not-allowed disabled:bg-white/10 disabled:text-white/35 disabled:shadow-none"
                      >
                        <AiOutlineSend className="text-xl" />
                      </button>
                    )}
                  </div>
                </form>
              </div>
            </main>
          </div>
          
          {/* Diagram review uses the existing React Flow renderer. */}
          {((activeTopology?.nodes?.length ?? 0) > 0 || topologiesLoading || topologyLoadError) && (
            <>

              <div
                className="
                  w-1
                  cursor-col-resize
                  bg-white/10
                  hover:bg-cyan-400
                  transition-colors
                "
                onMouseDown={(e) => {
                  e.preventDefault()
                  isResizingRef.current = true;
                  resizeStartX.current = e.clientX
                  resizeStartWidth.current = canvasWidth

                  document.body.style.userSelect = "none";
                  document.body.style.cursor = "col-resize";
                }}
              />

              <div

                style={{
                  width: `${canvasWidth}%`,
                  minWidth: "420px",
                }}

                className="
                  border-l
                border-white/10
                bg-zinc-100
                text-zinc-900
                ">
                <div className="flex h-full min-h-0 flex-col">
                  <div className="shrink-0 space-y-3 overflow-y-auto bg-slate-900 p-3 text-white [scrollbar-width:thin]">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-semibold">
                          {canvasView === "proposed" && activeProposal
                            ? activeProposal.status === "accepted" ? "Accepted Diagram Version" : "Proposed Diagram"
                            : "Original Diagram"}
                        </div>
                        <div className="truncate text-xs text-slate-300">
                          {activeSourceFile ?? "No indexed source selected"}
                        </div>
                      </div>
                      {topologyRecords.length > 0 && (
                        <select
                          aria-label="Select diagram source"
                          value={activeSourceChunkId ?? ""}
                          disabled={isCorrecting || decisionLoadingId !== null}
                          onChange={(event) => handleSelectSource(event.target.value)}
                          className="max-w-52 rounded-md border border-white/20 bg-slate-800 px-2 py-1 text-xs text-white disabled:opacity-60"
                        >
                          {!activeSourceChunkId && (
                            <option value="">Chat result without indexed source</option>
                          )}
                          {topologyRecords.map((record, index) => (
                            <option key={record.source_chunk_id} value={record.source_chunk_id}>
                              {record.source_file || "Unnamed diagram"} · {index + 1}
                            </option>
                          ))}
                        </select>
                      )}
                    </div>

                    {topologiesLoading && <p className="text-xs text-slate-300">Loading diagram sources…</p>}
                    {topologyLoadError && <p role="alert" className="text-xs text-red-300">{topologyLoadError}</p>}
                    {streamTopology && !activeSourceChunkId && (
                      <p className="text-xs text-amber-200">
                        This chat result has no matched source ID, so correction is unavailable until an indexed source is selected.
                      </p>
                    )}

                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => setCanvasView("original")}
                        aria-pressed={canvasView === "original"}
                        className={`rounded-md px-3 py-1.5 text-xs ${canvasView === "original" ? "bg-cyan-600" : "bg-slate-700 hover:bg-slate-600"}`}
                      >
                        Original
                      </button>
                      <button
                        type="button"
                        onClick={() => setCanvasView("proposed")}
                        disabled={!activeProposal}
                        aria-pressed={canvasView === "proposed"}
                        className={`rounded-md px-3 py-1.5 text-xs disabled:opacity-40 ${canvasView === "proposed" ? "bg-emerald-700" : "bg-slate-700 hover:bg-slate-600"}`}
                      >
                        {activeProposal?.status === "accepted" ? "Accepted version" : "Proposal"}
                      </button>
                    </div>

                    {sourceProposals.length > 0 && activeSourceChunkId && (
                      <label className="flex items-center gap-2 text-xs text-slate-200">
                        Proposal
                        <select
                          value={activeProposal?.correction_id ?? ""}
                          disabled={decisionLoadingId !== null}
                          onChange={(event) => setSelectedProposalBySource((current) => ({
                            ...current,
                            [activeSourceChunkId]: event.target.value,
                          }))}
                          className="min-w-0 flex-1 rounded-md border border-white/20 bg-slate-800 px-2 py-1 text-white"
                        >
                          {sourceProposals.map((proposal) => (
                            <option key={proposal.correction_id} value={proposal.correction_id}>
                              {proposal.correction_id.slice(0, 8)} · {proposal.status}
                            </option>
                          ))}
                        </select>
                      </label>
                    )}

                    <label className="block text-xs text-slate-200">
                      Optional correction requirements
                      <textarea
                        value={correctionRequirements}
                        onChange={(event) => setCorrectionRequirements(event.target.value)}
                        placeholder="Describe constraints for the proposed correction…"
                        rows={2}
                        disabled={isCorrecting}
                        className="mt-1 w-full resize-y rounded-md border border-white/15 bg-slate-800 p-2 text-sm text-white placeholder:text-slate-400"
                      />
                    </label>

                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={handleCorrectDiagram}
                        disabled={!activeSourceRecord || isCorrecting || decisionLoadingId !== null}
                        className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {isCorrecting ? "Generating proposal…" : sourceProposals.length ? "Generate another proposal" : "Generate proposal"}
                      </button>
                      {activeProposal && (
                        <>
                          <button
                            type="button"
                            onClick={() => handleCorrectionDecision("accept")}
                            disabled={
                              decisionLoadingId !== null ||
                              activeProposal.status !== "proposed" ||
                              activeProposal.validation.errors.length > 0
                            }
                            className="rounded-lg bg-cyan-700 px-3 py-2 text-xs font-semibold text-white hover:bg-cyan-600 disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            {decisionLoadingId === activeProposal.correction_id ? "Saving…" : "Accept"}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleCorrectionDecision("reject")}
                            disabled={decisionLoadingId !== null || activeProposal.status !== "proposed"}
                            className="rounded-lg border border-red-300/50 px-3 py-2 text-xs font-semibold text-red-100 hover:bg-red-900/50 disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            {decisionLoadingId === activeProposal.correction_id ? "Saving…" : "Reject"}
                          </button>
                        </>
                      )}
                    </div>
                    {correctionError && <p role="alert" className="text-xs text-red-300">{correctionError}</p>}
                    {activeProposal?.ui_error && <p role="alert" className="text-xs text-red-300">{activeProposal.ui_error}</p>}
                    {activeProposal?.ui_message && <p role="status" className="text-xs text-emerald-200">{activeProposal.ui_message}</p>}
                    {activeProposal && (
                      <div className="text-xs text-slate-300">
                        Proposal status: <span className="font-semibold capitalize text-white">{activeProposal.status}</span>
                        {activeProposal.version_id && <span> · Version {activeProposal.version_id.slice(0, 8)}</span>}
                      </div>
                    )}
                  </div>

                  {activeProposal && (
                    <details className="max-h-[34vh] min-h-0 shrink-0 overflow-y-auto border-b border-zinc-200 bg-white text-sm text-zinc-900 [scrollbar-width:thin]">
                      <summary className="sticky top-0 z-10 flex cursor-pointer list-none items-start justify-between gap-3 bg-white p-3 [&::-webkit-details-marker]:hidden">
                        <div className="min-w-0">
                          <span className="font-semibold">Proposal details</span>
                          <p className="mt-0.5 line-clamp-2 text-xs text-zinc-600">{activeProposal.summary}</p>
                        </div>
                        <span className="shrink-0 text-right text-xs text-zinc-500">
                          {activeProposal.proposed_changes.length} changes
                          {(activeProposal.validation.errors.length > 0 || activeProposal.validation.warnings.length > 0) && (
                            <span className="block">
                              {activeProposal.validation.errors.length} errors · {activeProposal.validation.warnings.length} warnings
                            </span>
                          )}
                        </span>
                      </summary>
                    <div className="space-y-3 px-3 pb-3">
                      <section>
                        <h3 className="font-semibold">Correction summary</h3>
                        <p className="mt-1 whitespace-pre-wrap">{activeProposal.summary}</p>
                      </section>

                      {activeProposal.proposed_changes.map((change, index) => (
                        <article key={`${change.operation}-${index}`} className="rounded-lg border border-zinc-200 bg-zinc-50 p-2.5">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <h4 className="font-semibold">{change.operation.replaceAll("_", " ")}</h4>
                            <span className="rounded-full bg-zinc-200 px-2 py-0.5 text-xs capitalize text-zinc-700">
                              Confidence: {change.confidence}
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-zinc-600">Target: {Object.values(change.target).join(" · ")}</p>
                          <p className="mt-2"><span className="font-medium">Reason:</span> {change.reason}</p>
                          {change.uncertainty && (
                            <p className="mt-1 text-amber-800"><span className="font-medium">Uncertainty:</span> {change.uncertainty}</p>
                          )}
                          <div className="mt-2 grid gap-2 sm:grid-cols-2">
                            <div>
                              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">Before</div>
                              <pre className="max-h-36 overflow-auto whitespace-pre-wrap break-words rounded bg-zinc-100 p-2 text-xs text-zinc-800">{change.before === null ? "—" : JSON.stringify(change.before, null, 2)}</pre>
                            </div>
                            <div>
                              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">After</div>
                              <pre className="max-h-36 overflow-auto whitespace-pre-wrap break-words rounded bg-zinc-100 p-2 text-xs text-zinc-800">{change.after === null ? "—" : JSON.stringify(change.after, null, 2)}</pre>
                            </div>
                          </div>
                        </article>
                      ))}

                      {activeProposal.proposed_changes.length === 0 && (
                        <p className="text-zinc-600">No topology changes were proposed.</p>
                      )}

                      {activeProposal.validation.errors.length > 0 && (
                        <section className="rounded-lg border border-red-400/40 bg-red-950/50 p-2.5 text-red-100">
                          <h4 className="font-semibold">Validation errors · acceptance disabled</h4>
                          <ul className="mt-1 list-disc pl-5">
                            {activeProposal.validation.errors.map((error, index) => <li key={index}>{error}</li>)}
                          </ul>
                        </section>
                      )}
                      {activeProposal.validation.warnings.length > 0 && (
                        <section className="rounded-lg border border-amber-400/40 bg-amber-950/40 p-2.5 text-amber-100">
                          <h4 className="font-semibold">Validation warnings</h4>
                          <ul className="mt-1 list-disc pl-5">
                            {activeProposal.validation.warnings.map((warning, index) => <li key={index}>{warning}</li>)}
                          </ul>
                        </section>
                      )}
                    </div>
                    </details>
                  )}

                  <div className="min-h-[240px] min-w-0 flex-1">
                    {displayedTopology && displayedTopology.nodes.length > 0 ? (
                      <InteractiveSchemaCanvas
                        graphPayload={{
                          topology: displayedTopology,
                          actions: canvasView === "original" ? visualActions : [],
                          edges: canvasView === "original" ? visualEdges : [],
                        }}
                      />
                    ) : (
                      <div className="p-4 text-sm text-zinc-600">
                        {topologiesLoading ? "Loading diagram sources…" : topologyLoadError || "No diagram topology is available for this conversation."}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}

        </section>
      </div>
    </div>
  );
}
