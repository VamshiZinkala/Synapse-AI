
export default function MessageComponent({
  data,
  isHuman,
}: {
  data: string;
  isHuman: boolean;
}) {
  return (
    <div className={`flex w-full ${isHuman ? "justify-end" : "justify-start"}`}>
      <div
        className={`flex min-w-0 max-w-[88%] items-end gap-3 md:max-w-[70%] ${isHuman ? "flex-row-reverse" : "flex-row"
          }`}
      >
        <div
          className={`relative min-w-0 break-words rounded-[1.35rem] border px-5 py-3.5 text-sm leading-6 shadow-2xl backdrop-blur-xl md:text-[0.95rem] ${isHuman
            ? "rounded-br-md border-cyan-200/25 bg-cyan-300/15 text-cyan-50 shadow-cyan-950/20"
            : "rounded-bl-md border-white/12 bg-white/8 text-zinc-100 shadow-black/25"
            }`}
        >
            <p className="whitespace-pre-wrap [overflow-wrap:anywhere] break-words">
              {data}
            </p>

        </div>
      </div>
    </div>
  );
}
