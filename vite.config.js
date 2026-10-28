import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig(({command})=>({
 base:'./',plugins:[react(),{name:'development-csp',transformIndexHtml(html){return command==='serve'?html.replace("script-src 'self';","script-src 'self' 'unsafe-inline';"):html;}}],
 build:{outDir:'dist',emptyOutDir:true,sourcemap:false,minify:'esbuild',rollupOptions:{output:{manualChunks:{charts:['recharts'],motion:['framer-motion']}}}},
 server:{host:'127.0.0.1',port:5173,strictPort:true},
}));
