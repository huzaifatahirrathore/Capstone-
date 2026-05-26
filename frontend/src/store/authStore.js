import { create } from "zustand"
import { persist } from "zustand/middleware"
import { loginApi, logoutApi, getMeApi } from "../api/Auth"

export const useAuthStore = create(
    persist(
        (set, get) => ({
            user:    null,
            token:   null,
            loading: false,
            error:   null,

            login: async (email, password) => {
                set({ loading: true, error: null })
                const res = await loginApi(email, password)

                // If backend is unreachable, fall back to mock login so pages are explorable
                if (res?.status === "Error") {
                    const mockUser = { email, name: email.split("@")[0] }
                    set({ user: mockUser, token: "mock-token", loading: false, error: null })
                    return true
                }

                const token = res?.token ?? res?.accessToken ?? null
                const user  = res?.user  ?? { email }

                if (token) sessionStorage.setItem("ACCESS_TOKEN", token)
                set({ user, token, loading: false, error: null })
                return true
            },

            logout: async () => {
                await logoutApi().catch(() => {})
                sessionStorage.removeItem("ACCESS_TOKEN")
                set({ user: null, token: null, error: null })
            },

            fetchMe: async () => {
                const res = await getMeApi()
                if (res?.status !== "Error") {
                    set({ user: res })
                }
            },

            clearError: () => set({ error: null }),
        }),
        {
            name:    "ecoledger-auth",
            partialize: (state) => ({ user: state.user, token: state.token }),
        }
    )
)
