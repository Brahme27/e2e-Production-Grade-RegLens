import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Minimal self-contained server for the Docker image (server.js + traced node_modules).
  output: "standalone",
  // cacheComponents/partialPrefetching are off on purpose: this console is a client-heavy
  // dashboard reading live data, so build-time static shells add constraints without benefit.
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
