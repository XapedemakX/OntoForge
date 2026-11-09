import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
// La documentation (docs/guide/*.md) et la table d'aide (backend/ontoforge/assistant/help_map.json) sont embarquées au build : elles vivent hors de frontend/.
export default defineConfig({ plugins: [react()], server: { fs: { allow: ['..'] }, proxy: { '/api': process.env.ONTOFORGE_API || 'http://localhost:8000' } } })
