import { SearchIcon, BellIcon } from "../common/Icons";

export function TopNav({ title, subtitle, actions }) {
  return (
    <header className="shrink-0 h-14 bg-[#A3431F] flex items-center justify-between px-6 z-30 shadow-md">
      <div className="flex items-center gap-2.5">
        <svg viewBox="0 0 24 26" width="22" height="22" fill="none">
          <line x1="12" y1="26" x2="12" y2="16" stroke="#EFE8DC" strokeWidth="1.5" strokeLinecap="round" />
          <circle cx="12" cy="16" r="2" fill="#00E6E6" />
          <line x1="12" y1="16" x2="5"  y2="10" stroke="#EFE8DC" strokeWidth="1.2" strokeLinecap="round" />
          <line x1="12" y1="16" x2="19" y2="10" stroke="#EFE8DC" strokeWidth="1.2" strokeLinecap="round" />
          <line x1="12" y1="16" x2="12" y2="7"  stroke="#EFE8DC" strokeWidth="1.2" strokeLinecap="round" />
          <circle cx="5"  cy="10" r="1.4" fill="#EFE8DC" fillOpacity="0.8" />
          <circle cx="19" cy="10" r="1.4" fill="#EFE8DC" fillOpacity="0.8" />
          <circle cx="12" cy="7"  r="1.4" fill="#EFE8DC" fillOpacity="0.8" />
        </svg>
        <span className="text-[#EFE8DC] font-bold text-lg tracking-wide select-none">EcoLedger</span>
        <span className="hidden sm:block h-4 w-px bg-[#EFE8DC]/25 mx-1" />
        {subtitle && (
          <span className="hidden sm:block text-[#EFE8DC]/50 text-xs tracking-widest uppercase font-medium select-none">
            {subtitle}
          </span>
        )}
        {title && (
          <>
            <span className="hidden sm:block h-4 w-px bg-[#EFE8DC]/25 mx-1" />
            <span className="hidden sm:block text-[#EFE8DC]/80 text-xs font-medium select-none">{title}</span>
          </>
        )}
      </div>

      <div className="flex items-center gap-3">
        {actions}
        <button className="text-[#EFE8DC]/65 hover:text-[#EFE8DC] transition-colors p-1.5 rounded-lg hover:bg-white/10">
          <SearchIcon />
        </button>
        <button className="relative text-[#EFE8DC]/65 hover:text-[#EFE8DC] transition-colors p-1.5 rounded-lg hover:bg-white/10">
          <BellIcon />
          <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-[#00E6E6] rounded-full" />
        </button>
        <div className="w-8 h-8 rounded-full bg-[#EFE8DC]/20 border-2 border-[#EFE8DC]/35 flex items-center justify-center text-[#EFE8DC] text-xs font-bold select-none">
          UI
        </div>
      </div>
    </header>
  );
}
