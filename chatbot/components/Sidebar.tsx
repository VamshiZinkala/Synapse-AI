import { FiMessageSquare, FiPlus, FiX } from "react-icons/fi";
import SidebarLoader from "./sidebarLoader";

interface Conversation {
  id: string;
  title: string;
}

interface SidebarProps {
  activeConversationId: string;
  conversations: Conversation[];
  isOpen: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onSelectConversation: (conversationId: string) => void;
  isConvLoaded: boolean;
}

export default function Sidebar({
  activeConversationId,
  conversations,
  isOpen,
  onClose,
  onNewChat,
  onSelectConversation,
  isConvLoaded
}: SidebarProps) {

  return (
    <>
      <div
        className={`fixed inset-0 z-30 bg-black/50 backdrop-blur-sm transition-opacity lg:hidden ${isOpen ? "opacity-100" : "pointer-events-none opacity-0"
          }`}
      />

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-white/10 bg-black/35 p-4 shadow-2xl shadow-black/40 backdrop-blur-2xl transition-transform duration-300 lg:static lg:translate-x-0 ${isOpen ? "translate-x-0" : "-translate-x-full"
          }`}
      >
        <div className="mb-5 flex items-center justify-between">
          <div>
            <p className="text-xl font-medium uppercase tracking-widest text-[#00cccc]"
            >
            Agent
          </p>
          <h2 className="mt-1 text-lg font-semibold text-white">Chats</h2>
        </div>
        <button
          type="button"
          aria-label="Close sidebar"
          onClick={onClose}
          className="grid size-9 place-items-center rounded-2xl border border-white/10 bg-white/5 text-zinc-200 transition hover:bg-white/10 lg:hidden"
        >
          <FiX />
        </button>
      </div>

      <button
        type="button"
        onClick={onNewChat}
        className="mb-5 flex items-center justify-center gap-2 rounded-2xl border border-cyan-200/25 bg-cyan-300/15 px-4 py-3 text-sm font-medium text-cyan-50 shadow-lg shadow-cyan-950/20 transition hover:bg-cyan-300/20"
      >
        <FiPlus className="text-lg" />
        New chat
      </button>

      <div className="min-h-0 flex-1 overflow-y-auto pr-1 [scrollbar-width:thin] [scrollbar-color:rgba(103,232,249,0.4)_transparent]">
        <p className="mb-2 px-2 text-xs font-medium uppercase tracking-[0.18em] text-zinc-500">
          Previous
        </p>
        <div className="space-y-1.5">
          {isConvLoaded ? conversations.map((conversation) => {
            const isActive = conversation.id === activeConversationId;

            return (
              <button
                key={conversation.id}
                type="button"
                onClick={() => onSelectConversation(conversation.id)}
                className={`flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left text-sm transition ${isActive
                    ? "border border-white/12 bg-white/12 text-white shadow-lg shadow-black/20"
                    : "text-zinc-400 hover:bg-white/7 hover:text-zinc-100"
                  }`}
              >
                <FiMessageSquare className="shrink-0 text-base" />
                <span className="min-w-0 flex-1 truncate">
                  {conversation.title}
                </span>
              </button>
            );
          }) : <SidebarLoader />}
        </div>
      </div>
    </aside >
    </>
  );
}


