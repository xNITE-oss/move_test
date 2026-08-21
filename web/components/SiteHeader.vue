<script setup lang="ts">
const open = ref(false)
const scrolled = ref(false)

function onScroll() {
  scrolled.value = window.scrollY > 24
}
onMounted(() => {
  onScroll()
  window.addEventListener('scroll', onScroll, { passive: true })
})
onBeforeUnmount(() => window.removeEventListener('scroll', onScroll))
</script>

<template>
  <header class="hdr" :class="{ scrolled }">
    <div class="container hdr-in">
      <NuxtLink to="/" class="brand">
        <span class="logo">
          <span class="sheen" />
          <span class="dot" />
        </span>
        <span class="brand-txt">Move<span class="grad-text">Space</span></span>
      </NuxtLink>

      <nav class="nav" :class="{ open }">
        <NuxtLink to="/" class="nav-link" @click="open = false">Bosh sahifa</NuxtLink>
        <a href="/#feed" class="nav-link" @click="open = false">Postlar</a>
        <a href="https://t.me" target="_blank" class="btn btn-primary sm">Telegram kanal</a>
      </nav>

      <button class="burger" :class="{ open }" aria-label="menu" @click="open = !open">
        <span /><span /><span />
      </button>
    </div>
    <div class="grad-line hdr-line" />
  </header>
</template>

<style scoped>
.hdr {
  position: sticky;
  top: 0;
  z-index: 50;
  padding: 18px 0;
  background: rgba(7, 11, 20, 0.35);
  backdrop-filter: blur(10px) saturate(140%);
  -webkit-backdrop-filter: blur(10px) saturate(140%);
  transition: padding 0.35s ease, background 0.35s ease, border-color 0.35s ease;
  animation: hdr-in 0.7s cubic-bezier(0.22, 1, 0.36, 1) both;
}
@keyframes hdr-in { from { transform: translateY(-100%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
.hdr.scrolled {
  padding: 11px 0;
  background: rgba(7, 11, 20, 0.72);
  backdrop-filter: blur(20px) saturate(150%);
  -webkit-backdrop-filter: blur(20px) saturate(150%);
}
.hdr-line { position: absolute; bottom: 0; left: 0; right: 0; opacity: 0.55; }
.hdr.scrolled .hdr-line { opacity: 0.9; }

.hdr-in { display: flex; align-items: center; justify-content: space-between; gap: 16px; }

.brand { display: flex; align-items: center; gap: 11px; font-family: var(--font-head); font-weight: 800; font-size: 1.25rem; }
.logo {
  position: relative;
  width: 36px; height: 36px; border-radius: 12px;
  background: var(--accent-grad);
  display: grid; place-items: center;
  overflow: hidden;
  animation: pulse-ring 3s ease-out infinite;
}
.logo .sheen {
  position: absolute; inset: -50%;
  background: conic-gradient(from 0deg, transparent, rgba(255,255,255,0.55), transparent 40%);
  animation: spin-slow 5s linear infinite;
}
.logo .dot { position: relative; width: 12px; height: 12px; border-radius: 50%; background: #04121a; z-index: 1; transition: transform 0.3s; }
.brand:hover .dot { transform: scale(0.8); }
.brand-txt { letter-spacing: -0.02em; }

.nav { display: flex; align-items: center; gap: 6px; }
.nav-link {
  position: relative;
  color: var(--text-dim);
  font-weight: 600; font-size: 0.95rem;
  padding: 8px 14px; border-radius: 10px;
  transition: color 0.18s;
}
.nav-link::after {
  content: '';
  position: absolute; left: 14px; right: 14px; bottom: 4px; height: 2px;
  background: var(--accent-grad); border-radius: 2px;
  transform: scaleX(0); transform-origin: left;
  transition: transform 0.28s cubic-bezier(0.22,1,0.36,1);
}
.nav-link:hover { color: var(--text); }
.nav-link:hover::after { transform: scaleX(1); }
.btn.sm { padding: 9px 18px; font-size: 0.88rem; }

.burger { display: none; flex-direction: column; gap: 5px; background: none; border: 0; cursor: pointer; padding: 8px; }
.burger span { width: 22px; height: 2px; background: var(--text); border-radius: 2px; transition: transform 0.3s, opacity 0.3s; }
.burger.open span:nth-child(1) { transform: translateY(7px) rotate(45deg); }
.burger.open span:nth-child(2) { opacity: 0; }
.burger.open span:nth-child(3) { transform: translateY(-7px) rotate(-45deg); }

@media (max-width: 720px) {
  .burger { display: flex; }
  .nav {
    position: absolute; top: 100%; right: 16px; left: 16px;
    flex-direction: column; align-items: stretch; gap: 6px;
    padding: 14px; margin-top: 10px;
    background: rgba(11, 17, 32, 0.94);
    border: 1px solid var(--glass-border); border-radius: 18px;
    backdrop-filter: blur(20px);
    display: none;
  }
  .nav.open { display: flex; animation: rise 0.3s ease both; }
  .nav-link { padding: 12px; }
}
</style>
