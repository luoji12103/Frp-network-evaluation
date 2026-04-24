import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  build: {
    manifest: true,
    outDir: '../controller/assets/dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        admin: resolve(__dirname, 'src/entries/admin/index.tsx'),
        public: resolve(__dirname, 'src/entries/public/index.tsx'),
        login: resolve(__dirname, 'src/entries/login/index.tsx')
      },
      output: {
        entryFileNames: 'js/[name].js',
        chunkFileNames: 'js/chunk-[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]'
      }
    }
  }
});
