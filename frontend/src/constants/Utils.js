export const formatErrorMessage = (error) => {
    if (!error) return "An unknown error occurred"
    if (typeof error === "string") return error
    if (Array.isArray(error)) return error.join(", ")
    if (typeof error === "object") return JSON.stringify(error)
    return String(error)
}
