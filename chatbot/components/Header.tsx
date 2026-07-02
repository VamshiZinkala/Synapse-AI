import { BsReverseLayoutTextSidebarReverse } from "react-icons/bs";

interface HeaderProps {
  title: string;
  onToggleSidebar: () => void;
}

export default function Header({ title, onToggleSidebar }: HeaderProps) {
  return (
    <header className="border-b border-white/10 bg-black/20 px-5 py-4 shadow-2xl backdrop-blur-2xl md:px-8">
      <div className="mx-auto flex max-w-4xl items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            aria-label="Open sidebar"
            onClick={onToggleSidebar}
            className="grid size-10 shrink-0 place-items-center rounded-2xl border border-white/10 bg-white/5 text-zinc-200 transition hover:bg-white/10 lg:hidden"
          >
            <BsReverseLayoutTextSidebarReverse className="text-lg" />
          </button>
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-cyan-200/70 sm:tracking-[0.28em]">
              Chat
            </p>
            <h1 className="mt-1 truncate text-xl font-semibold text-white">
              {title}
            </h1>
          </div>
        </div>
        {/* <div className="hidden shrink-0 items-center gap-2 rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1.5 text-xs font-medium text-emerald-100 shadow-lg shadow-emerald-950/20 backdrop-blur-xl sm:flex">
          <span className="size-2 rounded-full bg-emerald-300 shadow-[0_0_18px_rgba(110,231,183,0.8)]" />
          Online
        </div> */}
      </div>
    </header>
  );
}
