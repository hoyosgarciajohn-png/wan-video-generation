import { defineConfig } from "vite";
export default defineConfig({
  publicDir: "../../fixtures",
  build: {
    commonjsOptions: { include: [/node_modules/, /src\/generated\/.*\.cjs$/] },
  },
  server: {
    host: "127.0.0.1",
    proxy: { "/v1/studio": "http://127.0.0.1:8787" },
  },
});
