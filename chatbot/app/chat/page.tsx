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

type AttachmentState = {
  id: string;
  file: File;
  status: 'uploading' | 'success' | 'error';
  errorMsg?: string;
};

const getConversationTitle = (content: string) => {
  const normalizedContent = content.replace(/\s+/g, " ").trim();
  if (!normalizedContent) return "New Chat";
  return normalizedContent.length > 34 ? `${normalizedContent.slice(0, 34)}...` : normalizedContent;
};


const user_id = 'test_user_id'
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

  const [activeSourceFile, setActiveSourceFile] = useState<string | null>(null);

  const [topologyCache, setTopologyCache] = useState<Record<string, any>>({})

  const [visualActions, setVisualActions] = useState<any[]>([])

  const [visualEdges, setVisualEdges] = useState<any[]>([]);
  const activeConversation = useMemo(() => {
    return conversations.find((conversation) => conversation.id === activeConversationId) ?? conversations[0]
  }, [activeConversationId, conversations])

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
    console.log("ACTIVE GRAPH DATA:", topologyCache);
  }, [topologyCache]);

  useEffect(() => {
    console.log("VISUAL ACTIONS", visualActions);
  }, [visualActions]);

  useEffect(() => {
    console.log("VISUAL EDGES", visualEdges);
  }, [visualEdges]);
  useEffect(() => {
    if (!activeConversationId) return;

    fetch(`http://localhost:8000/conversation/${activeConversationId}/topologies`)
      .then(res => res.json())
      .then(data => {
        const cache = data.topologies || {}
        setTopologyCache(cache)

        const files = Object.keys(cache)
        if (files.length > 0) {
          setActiveSourceFile(files[files.length - 1])
        }
      }).catch(console.error)
  }, [activeConversationId])

  useEffect(() => {
    console.log("ACTIVE DIAGRAM:", activeSourceFile);
  }, [activeSourceFile]);

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


                if (completeGraphPayload.source_file) {
                  setActiveSourceFile(completeGraphPayload.source_file)
                }


                if (completeGraphPayload.topology && completeGraphPayload.source_file) {
                  setTopologyCache(prev => ({
                    ...prev,
                    [completeGraphPayload.source_file]:
                      completeGraphPayload.topology
                  }));
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

  const activeTopology = activeSourceFile ? topologyCache[activeSourceFile] : null;

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
          {/* Schema Canvas Side Panel */}
          {activeTopology?.nodes?.length > 0 && (
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
                bg-slate-50
                text-black
                ">
                <InteractiveSchemaCanvas graphPayload={{
                  topology: activeTopology,
                  actions: visualActions,
                  edges: visualEdges
                }} />
              </div>
            </>
          )}

        </section>
      </div>
    </div>
  );
}
