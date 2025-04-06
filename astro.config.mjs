import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  integrations: [tailwind()],
  site: 'https://skazempour.netlify.app', // This will be updated with your actual domain
  base: '/',
  output: 'static'
});