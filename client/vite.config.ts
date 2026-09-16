import { defineConfig } from "vite";

// Dev: run the client on :5173 and proxy the WebSocket + API to the FastAPI
// backend on :8000. This avoids CORS entirely and lets the browser talk to a
// single same-origin endpoint, exactly like production.
export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/ws": {
        target: "ws://127.0.0.1:8000",
        ws: true,
      },
      "/health": {
        target: "http://127.0.0.1:8000",
      },
    },
  },
});
