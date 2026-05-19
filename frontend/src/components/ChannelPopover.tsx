import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { CHANNELS, type Channel } from "../lib/api";

interface Props {
  value: Channel;
  onChange: (channel: Channel) => void;
}

export function ChannelPopover({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative flex">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Mapping channel"
        onClick={() => setOpen((v) => !v)}
        className="flex h-full flex-1 flex-col items-start justify-center gap-px self-stretch rounded-l-xl border-r border-rail px-4 pl-[18px] py-0 text-left transition-colors hover:bg-cream-100"
      >
        <span className="font-sans text-[9.5px] font-semibold uppercase leading-none tracking-eyebrow text-cream-400">
          channel
        </span>
        <span className="mt-1 inline-flex items-center gap-1 font-mono text-[13.5px] font-medium leading-tight text-ink">
          <span>{value}</span>
          <ChevronDown size={13} strokeWidth={2.25} className="text-cream-600" />
        </span>
      </button>

      {open && (
        <div
          role="listbox"
          aria-label="Channel"
          className="absolute left-0 top-[calc(100%+6px)] z-40 min-w-[200px] rounded-xl border border-rail bg-white p-1.5 shadow-dropdown"
        >
          {CHANNELS.map((c) => (
            <button
              key={c.value}
              role="radio"
              aria-checked={c.value === value}
              onClick={() => {
                onChange(c.value);
                setOpen(false);
              }}
              className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left font-mono text-[13.5px] text-ink hover:bg-cream-100 aria-checked:bg-cream-100 aria-checked:font-medium"
            >
              <span>{c.label}</span>
              {c.value === value && (
                <span className="font-sans text-[10.5px] font-semibold uppercase tracking-eyebrow text-cream-400">
                  current
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
