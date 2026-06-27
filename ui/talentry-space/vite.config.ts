import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Manual chunking keeps the initial JS payload small: three.js + r3f are
// only needed for the storytelling section which lives below the fold, so
// they ship as a separate chunk that the browser can prefetch in the
// background.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    chunkSizeWarningLimit: 800,
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          three: ["three"],
          r3f: ["@react-three/fiber", "@react-three/drei"],
          framer: ["framer-motion"],
          diff: ["diff"],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:7860" },
  },
});
