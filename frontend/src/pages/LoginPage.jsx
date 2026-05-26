import { useState } from "react";
import {
  TreeNetworkIcon,
  EyeIcon,
  EyeOffIcon,
  SpinnerIcon,
} from "../common/Icons";

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [form, setForm] = useState({ email: "", password: "" });
  const [loading, setLoading] = useState(false);

  const handleChange = (e) =>
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!form.email || !form.password) return;
    setLoading(true);
    setTimeout(() => setLoading(false), 1800);
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-12 h-screen overflow-hidden font-sans">
      <div className="md:col-span-5 bg-[#A3431F] relative flex flex-col justify-center items-center px-10 overflow-hidden min-h-screen md:min-h-0">
        <div className="absolute -top-32 -left-32 w-96 h-96 rounded-full border border-[#EFE8DC]/[0.07] pointer-events-none" />
        <div className="absolute -top-20 -left-20 w-64 h-64 rounded-full border border-[#EFE8DC]/[0.04] pointer-events-none" />
        <div className="absolute -bottom-40 -right-20 w-[30rem] h-[30rem] rounded-full border border-[#EFE8DC]/[0.06] pointer-events-none" />
        <div className="absolute -bottom-28 -right-8  w-[20rem] h-[20rem] rounded-full border border-[#EFE8DC]/[0.04] pointer-events-none" />

        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(ellipse 90% 55% at 50% -8%, rgba(194,93,54,0.45) 0%, transparent 68%)",
          }}
        />

        <div className="w-full max-w-[330px] relative z-10">
          <div className="flex flex-col items-center mb-9">
            <div className="w-[3.25rem] h-[3.25rem]">
              <TreeNetworkIcon />
            </div>
            <h1 className="text-[#EFE8DC] text-[1.75rem] font-bold tracking-wide mt-3 leading-none select-none">
              EcoLedger
            </h1>
            <p className="text-[#EFE8DC]/40 text-[0.62rem] tracking-[0.24em] uppercase mt-2 font-medium select-none">
              Enterprise Platform
            </p>
          </div>

          {/* Divider */}
          <div className="w-full h-px bg-[#EFE8DC]/[0.13] mb-8" />

          <form onSubmit={handleSubmit} noValidate className="space-y-5">
            <div className="space-y-[0.38rem]">
              <label
                htmlFor="login-email"
                className="block text-[#EFE8DC]/70 text-[0.66rem] font-semibold tracking-[0.16em] uppercase"
              >
                Company Email
              </label>
              <input
                id="login-email"
                name="email"
                type="email"
                autoComplete="email"
                value={form.email}
                onChange={handleChange}
                placeholder="you@company.com"
                className="
                  w-full bg-[#6B2810]/50 border border-[#EFE8DC]/[0.17]
                  rounded-apps text-[#EFE8DC] text-sm
                  px-4 py-2
                  outline-none transition-all duration-200
                  placeholder:text-[#EFE8DC]/28
                  focus:border-[#EFE8DC]/45 focus:bg-[#6B2810]/70
                "
              />
            </div>

            <div className="space-y-[0.38rem]">
              <label
                htmlFor="login-password"
                className="block text-[#EFE8DC]/70 text-[0.66rem] font-semibold tracking-[0.16em] uppercase"
              >
                Password
              </label>
              <div className="relative">
                <input
                  id="login-password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  value={form.password}
                  onChange={handleChange}
                  placeholder="••••••••••••"
                  className="
                    w-full bg-[#6B2810]/50 border border-[#EFE8DC]/[0.17]
                    rounded-apps text-[#EFE8DC] text-sm
                    px-4 py-2 pr-11
                    outline-none transition-all duration-200
                    placeholder:text-[#EFE8DC]/28
                    focus:border-[#EFE8DC]/45 focus:bg-[#6B2810]/70
                  "
                />
                <button
                  type="button"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowPassword((v) => !v)}
                  className="
                    absolute right-3.5 top-1/2 -translate-y-1/2
                    text-[#EFE8DC]/38 hover:text-[#EFE8DC]/75
                    transition-colors duration-150
                  "
                >
                  {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="
                w-full mt-1
                bg-[#008080] hover:bg-[#006666]
                disabled:opacity-55 disabled:cursor-not-allowed
                text-white text-[0.82rem] font-semibold tracking-[0.07em]
                py-2 rounded-apps
                flex items-center justify-center gap-2.5
                transition-colors duration-200 cursor-pointer
              "
            >
              {loading && <SpinnerIcon />}
              {loading ? "Signing In…" : "Sign In"}
            </button>
          </form>

          <div className="mt-[1.6rem] flex flex-col items-center gap-[0.6rem]">
            <a
              href="#"
              className="text-[#EFE8DC]/48 hover:text-[#EFE8DC]/82 text-[0.8rem] transition-colors duration-150 underline-offset-2 hover:underline"
            >
              Forgot Password?
            </a>
            <a
              href="#"
              className="text-[#EFE8DC]/48 hover:text-[#EFE8DC]/82 text-[0.8rem] transition-colors duration-150 underline-offset-2 hover:underline"
            >
              Request Enterprise Access
            </a>
          </div>
        </div>

        <p className="absolute bottom-5 text-[#EFE8DC]/60 text-[0.68rem] tracking-wide select-none">
          © 2025 EcoLedger Inc. All rights reserved.
        </p>
      </div>

      <div className="hidden md:block md:col-span-7 relative overflow-hidden">
        <img
          src="/Login.avif"
          alt="Satellite view of forest carbon monitoring zones"
          className="absolute inset-0 w-full h-full object-cover object-center"
          draggable={false}
        />

        <div className="absolute inset-0 bg-gradient-to-r from-[#A3431F]/75 via-[#8C3418]/20 to-transparent" />

        <div className="absolute inset-0 bg-gradient-to-b from-black/30 via-transparent to-transparent" />

        <div className="absolute inset-0 bg-gradient-to-t from-black/72 via-black/20 to-transparent" />

        <div className="absolute bottom-0 left-0 right-0 px-10 pb-9">
          <div className="flex items-center gap-2 mb-3">
            <span className="block h-px w-6 bg-[#008080]" />
            <span className="text-[#EFE8DC] text-xs tracking-[0.22em] uppercase font-semibold">
              AI-Powered Forest Intelligence
            </span>
          </div>

          <div className="mt-4 flex items-center gap-1.5">
            <span className="block h-[3px] w-8  bg-[#008080]   rounded-full" />
            <span className="block h-[3px] w-3  bg-white/22    rounded-full" />
            <span className="block h-[3px] w-3  bg-white/22    rounded-full" />
          </div>
        </div>
      </div>
    </div>
  );
}
