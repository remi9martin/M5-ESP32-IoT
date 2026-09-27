import { defineConfig, loadEnv } from 'vite';

// Local dev only. In AI Studio the key is supplied by the platform.
// Note: `vite build` inlines the key into the bundle, so never deploy a build publicly.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return {
    server: { port: 3000, host: '0.0.0.0' },
    define: { 'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY) },
  };
});
