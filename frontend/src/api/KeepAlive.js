import { sendGet } from "./Generic"

export const keepAlive = () => {
    return sendGet(`KeepAlive`)
}
