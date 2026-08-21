<script setup lang="ts">
const open = ref(false)
const scrolled = ref(false)

function onScroll() {
  scrolled.value = window.scrollY > 16
}
onMounted(() => {
  onScroll()
  window.addEventListener('scroll', onScroll, { passive: true })
})
onBeforeUnmount(() => window.removeEventListener('scroll', onScroll))
</script>

<template>
  <div class="hdr-wrap">
    <header class="pill-nav" :class="{ scrolled }">
      <NuxtLink to="/" class="brand">
        <span class="logo"><span class="sheen" /><span class="dot" /></span>
        <span class="brand-txt">Move<span class="grad-text">Space</span></span>
      </NuxtLink>

      <nav class="nav" :class="{ open }">
        <NuxtLink to="/" class="nav-pill" @click="open = false">
          <svg viewBox="0 0 24 24" class="ic"><path d="M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          Bosh sahifa
        </NuxtLink>
        <a href="/#feed" class="nav-pill" @click="open = false">
          <svg viewBox="0 0 24 24" class="ic"><path d="M4 6h16M4 12h16M4 18h10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          Postlar
        </a>
        <a href="/#rubrikalar" class="nav-pill" @click="open = false">
          <svg viewBox="0 0 24 24" class="ic"><path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>
          Rubrikalar
        </a>
      </nav>

      <div class="right">
        <a href="https://t.me" target="_blank" class="btn btn-primary sm tg">Telegram kanal</a>
        <a href="https://t.me" target="_blank" class="circle-btn" aria-label="Telegram">
          <svg viewBox="0 0 24 24" width="20" height="20"><path d="M7 17L17 7M17 7H9M17 7v8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </a>
        <button class="burger" :class="{ open }" aria-label="menu" @click="open = !open">
          <span /><span /><span />
        </button>
      </div>
    </header>
  </div>
</template>

<style scoped>
.hdr-wrap {
  position: sticky;
  top: 0;
  z-index: 50;
  padding: 16px 16px 0;
  animation: hdr-in 0.7s cubic-bezier(0.22, 1, 0.36, 1) both;
}
@keyframes hdr-in { from { transform: translateY(-20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

.pill-nav {
  max-width: 1160px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 12px 12px 22px;
  border-radius: 999px;
  background: rgba(11, 17, 32, 0.55);
  border: 1px solid var(--glass-border);
  backdrop-filter: blur(20px) saturate(150%);
  -webkit-backdrop-filter: blur(20px) saturate(150%);
  box-shadow: 0 16px 40px -22px rgba(0, 0, 0, 0.8);
  transition: background 0.35s ease, box-shadow 0.35s ease, transform 0.35s ease;
}
.pill-nav.scrolled { background: rgba(9, 14, 26, 0.82); box-shadow: 0 18px 44px -20px rgba(0, 0, 0, 0.9); }

.brand { display: flex; align-items: center; gap: 11px; font-family: var(--font-head); font-weight: 800; font-size: 1.2rem; }
.logo {
  position: relative; width: 36px; height: 36px; border-radius: 12px;
  background: var(--accent-grad); display: grid; place-items: center; overflow: hidden;
  animation: pulse-ring 3s ease-out infinite;
}
.logo .sheen { position: absolute; inset: -50%; background: conic-gradient(from 0deg, transparent, rgba(255,255,255,0.55), transparent 40%); animation: spin-slow 5s linear infinite; }
.logo .dot { position: relative; width: 12px; height: 12px; border-radius: 50%; background: #04121a; z-index: 1; }
.brand-txt { letter-spacing: -0.02em; }

.nav { display: flex; align-items: center; gap: 4px; }
.nav-pill {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 9px 16px; border-radius: 999px;
  color: var(--text-dim); font-weight: 600; font-size: 0.92rem;
  border: 1px solid transparent;
  transition: all 0.18s ease;
}
.nav-pill .ic { width: 17px; height: 17px; }
.nav-pill:hover { color: var(--text); background: var(--glass); border-color: var(--glass-border); }
.router-link-exact-active.nav-pill { color: var(--text); background: var(--glass); border-color: var(--glass-border); }

.right { display: flex; align-items: center; gap: 10px; }
.btn.sm { padding: 11px 20px; font-size: 0.9rem; }
.circle-btn { width: 46px; height: 46px; }

.burger { display: none; flex-direction: column; gap: 5px; background: none; border: 0; cursor: pointer; padding: 8px; }
.burger span { width: 22px; height: 2px; background: var(--text); border-radius: 2px; transition: transform 0.3s, opacity 0.3s; }
.burger.open span:nth-child(1) { transform: translateY(7px) rotate(45deg); }
.burger.open span:nth-child(2) { opacity: 0; }
.burger.open span:nth-child(3) { transform: translateY(-7px) rotate(-45deg); }

@media (max-width: 860px) {
  .tg { display: none; }
}
@media (max-width: 720px) {
  .burger { display: flex; }
  .circle-btn { display: none; }
  .nav {
    position: absolute; top: calc(100% + 10px); right: 0; left: 0;
    flex-direction: column; align-items: stretch; gap: 6px;
    padding: 14px;
    background: rgba(11, 17, 32, 0.95);
    border: 1px solid var(--glass-border); border-radius: 24px;
    backdrop-filter: blur(20px);
    display: none;
  }
  .nav.open { display: flex; animation: rise 0.3s ease both; }
  .nav-pill { padding: 13px 16px; }
}
</style>
