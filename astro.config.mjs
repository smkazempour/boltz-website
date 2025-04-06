import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  site: 'https://smkazempour.github.io',
  base: '/boltz-website',
  outDir: 'docs',
  integrations: [tailwind()]
});