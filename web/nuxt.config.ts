// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-01-01',
  devtools: { enabled: false },
  // Statik SPA — serverda Node kerak emas, Caddy fayllarni beradi.
  // Kontent brauzerda /api dan yuklanadi (har doim yangi). SEO keyin SSR bilan.
  ssr: false,

  css: ['~/assets/css/main.css'],

  runtimeConfig: {
    // Server-side (SSR) API manzili
    apiBase: process.env.API_BASE || 'https://movespace.uz',
    public: {
      // Brauzer /api ni ishlatadi (dev'da proxy, prod'da bir xil domen)
      apiBase: '/api',
    },
  },

  app: {
    head: {
      htmlAttrs: { lang: 'uz' },
      title: 'Move Space — harakat, sarguzasht, tabiat',
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        {
          name: 'description',
          content:
            "Move Space — O'zbekistonda yugurish, hiking, velosiped, camping va faol hayot haqida amaliy postlar.",
        },
        { name: 'theme-color', content: '#0a0f1a' },
      ],
      link: [
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Sora:wght@600;700;800&display=swap',
        },
      ],
    },
  },

  // Dev'da CORS'siz API'ga ulanish. API_BASE bilan boshqariladi
  // (lokal ishlashda SSH tunnel: http://localhost:8000).
  nitro: {
    devProxy: {
      '/api': {
        target: `${process.env.API_BASE || 'https://movespace.uz'}/api`,
        changeOrigin: true,
      },
    },
  },
})
