import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  site: 'https://smkazempour.com',
  base: '/',
  outDir: 'docs',
  integrations: [tailwind()]
});
