<script setup lang="ts">
const year = new Date().getFullYear()
</script>

<template>
  <footer class="ft">
    <div class="container ft-in glass">
      <div class="col brand-col">
        <div class="brand">
          <span class="logo"><span class="dot" /></span>
          Move<span class="grad-text">Space</span>
        </div>
        <p class="tag">Harakat, sarguzasht va tabiat — O'zbekiston uchun.</p>
      </div>
      <div class="col">
        <h4>Rubrikalar</h4>
        <span class="muted">Yugurish · Hiking · Cycling · Camping · Active Life</span>
      </div>
      <div class="col">
        <h4>Bog'lanish</h4>
        <a href="https://t.me" target="_blank" class="link">Telegram kanal</a>
        <a href="/" class="link">movespace.uz</a>
      </div>
    </div>
    <p class="copy">© {{ year }} Move Space · Barcha huquqlar himoyalangan</p>
  </footer>
</template>

<style scoped>
.ft { margin-top: 90px; padding-bottom: 30px; }
.ft-in { display: grid; grid-template-columns: 1.4fr 1fr 1fr; gap: 30px; padding: 40px; }
.brand { display: flex; align-items: center; gap: 10px; font-family: var(--font-head); font-weight: 800; font-size: 1.2rem; margin-bottom: 10px; }
.logo { width: 30px; height: 30px; border-radius: 10px; background: var(--accent-grad); display: grid; place-items: center; }
.logo .dot { width: 9px; height: 9px; border-radius: 50%; background: #04121a; }
.tag { color: var(--text-dim); font-size: 0.92rem; max-width: 280px; }
h4 { font-family: var(--font-head); font-size: 0.95rem; margin-bottom: 12px; }
.muted { color: var(--text-faint); font-size: 0.9rem; }
.link { display: block; color: var(--text-dim); font-size: 0.92rem; padding: 4px 0; transition: color 0.15s; }
.link:hover { color: var(--a2); }
.copy { text-align: center; color: var(--text-faint); font-size: 0.85rem; margin-top: 26px; }
@media (max-width: 720px) {
  .ft-in { grid-template-columns: 1fr; gap: 24px; padding: 30px; }
}
</style>
