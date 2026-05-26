import { sendPost, sendGet } from "./generic"

export const loginApi = (email, password) =>
    sendPost("auth/login", { email, password })

export const logoutApi = () =>
    sendPost("auth/logout", {})

export const getMeApi = () =>
    sendGet("auth/me")
