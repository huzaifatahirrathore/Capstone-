import { useNavigate, useLocation } from "react-router-dom"
import { SearchIcon, BellIcon } from "../common/Icons"
import { useAuthStore } from "../store/authStore"

function SatelliteIcon() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
      <path d="M4.93 4.93l2.12 2.12M16.95 16.95l2.12 2.12M4.93 19.07l2.12-2.12M16.95 7.05l2.12-2.12" />
    </svg>
  )
}

export function TopNav({ title, subtitle, actions }) {
  const navigate  = useNavigate()
  const location  = useLocation()
  const { user, logout } = useAuthStore()

  const handleLogout = async () => {
    await logout()
    navigate("/")
  }

  const initials = user?.name
    ? user.name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2)
    : user?.email?.slice(0, 2).toUpperCase() ?? "UI"

  const navLinks = [
    { label: "Dashboard",   path: "/dashboard" },
    { label: "AI Analysis", path: "/analysis",  icon: <SatelliteIcon /> },
  ]

  return (
    <header className="shrink-0 h-14 bg-[#A3431F] flex items-center justify-between px-6 z-30 shadow-md">
      {/* Left: Logo + breadcrumb */}
      <div className="flex items-center gap-2.5">
        <button onClick={() => navigate("/dashboard")} className="flex items-center gap-2 focus:outline-none">
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
        </button>

        <span className="hidden sm:block h-4 w-px bg-[#EFE8DC]/25 mx-1" />

        {/* Nav links */}
        <nav className="hidden sm:flex items-center gap-1">
          {navLinks.map(({ label, path, icon }) => {
            const active = location.pathname === path
            return (
              <button
                key={path}
                onClick={() => navigate(path)}
                className={`
                  flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-150
                  ${active
                    ? "bg-white/15 text-[#EFE8DC]"
                    : "text-[#EFE8DC]/60 hover:text-[#EFE8DC] hover:bg-white/10"
                  }
                `}
              >
                {icon}
                {label}
              </button>
            )
          })}
        </nav>

        {title && (
          <>
            <span className="hidden sm:block h-4 w-px bg-[#EFE8DC]/25 mx-1" />
            <span className="hidden sm:block text-[#EFE8DC]/60 text-xs font-medium select-none truncate max-w-[200px]">
              {title}
            </span>
          </>
        )}
      </div>

      {/* Right: actions + icons + avatar */}
      <div className="flex items-center gap-2">
        {actions}
        <button className="text-[#EFE8DC]/65 hover:text-[#EFE8DC] transition-colors p-1.5 rounded-lg hover:bg-white/10">
          <SearchIcon />
        </button>
        <button className="relative text-[#EFE8DC]/65 hover:text-[#EFE8DC] transition-colors p-1.5 rounded-lg hover:bg-white/10">
          <BellIcon />
          <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-[#00E6E6] rounded-full" />
        </button>

        {/* Avatar + logout */}
        <div className="relative group">
          <button className="w-8 h-8 rounded-full bg-[#EFE8DC]/20 border-2 border-[#EFE8DC]/35 flex items-center justify-center text-[#EFE8DC] text-xs font-bold select-none hover:bg-[#EFE8DC]/30 transition-colors">
            {initials}
          </button>
          {/* Dropdown */}
          <div className="absolute right-0 top-full mt-2 w-40 bg-white rounded-xl shadow-xl border border-[#E5DDD0] py-1 opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-all duration-150 z-50">
            {user?.email && (
              <p className="px-3 py-2 text-[#8C7B68] text-[0.65rem] truncate border-b border-[#F0EBE3]">
                {user.email}
              </p>
            )}
            <button
              onClick={handleLogout}
              className="w-full text-left px-3 py-2 text-[#A3431F] text-xs font-semibold hover:bg-[#FDF8F5] transition-colors"
            >
              Sign Out
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}
