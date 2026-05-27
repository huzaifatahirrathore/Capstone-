export const getBaseApiUrl = () => {
    if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
        return "https://localhost:7277/api/"
    } else if (window.location.hostname.includes("windows")) {
        //Replace the URL with the URL of your deployed project
        return "https://wireframes****.z21.web.core.windows.net/api/"
    } else {
        return "/api/"
    }
}

// Node.js backend (Express on port 3000)
export const getNodeBackendUrl = () => {
    if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
        return "http://localhost:3000/"
    }
    return "/api/"
}
