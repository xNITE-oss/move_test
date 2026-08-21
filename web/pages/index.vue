<script setup lang="ts">
import type { SitePost } from '~/composables/useApi'

const { meta, all } = useRubrics()

const { data, pending, error } = await useAsyncData<SitePost[]>(
  'site-posts',
  () => $fetch(apiUrl('/api/site/posts?limit=60')),
  { default: () => [] },
)

const active = ref<string>('all')

const rubricsInPosts = computed(() => {
  const keys = new Set<string>()
  ;(data.value || []).forEach((p) => p.rubric && keys.add(p.rubric))
  return [...keys]
})

const rubricList = computed(() =>
  Object.entries(all).map(([key, m]) => ({
    key,
    ...m,
    count: (data.value || []).filter((p) => p.rubric === key).length,
  })),
)

const filtered = computed(() => {
  const list = data.value || []
  return active.value === 'all' ? list : list.filter((p) => p.rubric === active.value)
})

const featured = computed(() => (data.value || [])[0])

function pickRubric(key: string) {
  active.value = key
  if (import.meta.client) {
    document.getElementById('feed')?.scrollIntoView({ behavior: 'smooth' })
  }
}
</script>

<template>
  <div class="container page">
    <!-- ─── HERO BENTO ─── -->
    <section class="hero-bento">
      <div class="bento-card hero-card" v-reveal>
        <span class="eyebrow">✦ O'zbekistonda faol hayot media-kanali</span>
        <h1 class="hh">Harakat — bu <span class="grad-text">makon</span>.<br />Tabiat esa maydon.</h1>
        <p class="sub">
          Yugurish, hiking, velosiped va camping bo'yicha amaliy postlar — har
          biri tekshirilgan, aniq va O'zbekiston sharoitiga moslangan.
        </p>
        <div class="cta-row">
          <a href="#feed" class="btn btn-primary">Postlarni ko'rish</a>
          <a href="#feed" class="circle-btn" aria-label="pastga">
            <svg viewBox="0 0 24 24" width="20" height="20"><path d="M12 5v14M6 13l6 6 6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </a>
        </div>
        <div class="hero-foot">
          <div class="ring"><span><CountUp :to="(data || []).length" /></span></div>
          <div class="avatars">
            <span
              v-for="(r, i) in rubricList.slice(0, 4)" :key="r.key"
              class="ava" :style="{ background: r.color + '33', borderColor: r.color + '66', zIndex: 4 - i }"
            >{{ r.emoji }}</span>
          </div>
          <div class="foot-txt">
            <b><CountUp :to="(data || []).length" suffix="+" /> post tayyor</b>
            <span>Har biri sifat tekshiruvidan o'tgan</span>
          </div>
        </div>
      </div>

      <NuxtLink
        v-if="featured"
        :to="`/post/${featured.slug}`"
        class="bento-card feature-card"
        v-reveal="120"
        :style="{ '--rc': meta(featured.rubric).color }"
      >
        <div class="f-glow" />
        <div class="f-top">
          <span class="badge" :style="{ color: meta(featured.rubric).color, borderColor: meta(featured.rubric).color + '55' }">
            {{ meta(featured.rubric).emoji }} {{ meta(featured.rubric).label }}
          </span>
          <span class="f-tag">✦ Tavsiya</span>
        </div>
        <h2 class="f-title">{{ featured.title }}</h2>
        <p class="f-lead">{{ featured.lead }}</p>
        <div class="f-cta">
          <span>O'qishni boshlash</span>
          <span class="circle-btn ghost sm-circle">
            <svg viewBox="0 0 24 24" width="18" height="18"><path d="M7 17L17 7M17 7H9M17 7v8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </span>
        </div>
      </NuxtLink>
    </section>

    <!-- ─── BENTO 3 ─── -->
    <section id="rubrikalar" class="bento-3">
      <div class="bento-card list-card" v-reveal>
        <div class="card-head">
          <h3>Rubrikalar</h3>
          <span class="muted">{{ rubricList.length }} ta</span>
        </div>
        <div class="rlist">
          <button v-for="r in rubricList" :key="r.key" class="ritem" @click="pickRubric(r.key)">
            <span class="remoji" :style="{ background: r.color + '22', color: r.color }">{{ r.emoji }}</span>
            <span class="rname">{{ r.label }}</span>
            <span class="rcount">{{ r.count }}</span>
          </button>
        </div>
      </div>

      <div class="bento-card promo-card" v-reveal="100">
        <div class="p-glow" />
        <div class="p-badge">Telegram</div>
        <h3>Kanalga birinchi<br />bo'lib qo'shiling</h3>
        <p>Har yangi post kanalda darrov chiqadi — kutmasdan o'qing.</p>
        <a href="https://t.me" target="_blank" class="btn btn-primary">
          Obuna bo'lish
          <svg viewBox="0 0 24 24" width="17" height="17"><path d="M7 17L17 7M17 7H9M17 7v8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </a>
      </div>

      <div class="bento-card stat-card" v-reveal="200">
        <h3>Nega Move Space?</h3>
        <div class="stat-grid">
          <div class="s"><b class="grad-text"><CountUp :to="(data || []).length" suffix="+" /></b><span>Post</span></div>
          <div class="s"><b class="grad-text"><CountUp :to="rubricList.length" /></b><span>Rubrika</span></div>
          <div class="s"><b class="grad-text"><CountUp :to="100" suffix="%" /></b><span>Tekshirilgan</span></div>
        </div>
      </div>
    </section>

    <!-- ─── FEED ─── -->
    <section id="feed" class="feed">
      <div class="feed-head" v-reveal>
        <h2>Barcha postlar</h2>
        <div class="filters">
          <button class="chip" :class="{ active: active === 'all' }" @click="active = 'all'">Hammasi</button>
          <button
            v-for="k in rubricsInPosts" :key="k"
            class="chip" :class="{ active: active === k }" @click="active = k"
          >{{ meta(k).emoji }} {{ meta(k).label }}</button>
        </div>
      </div>

      <div v-if="pending" class="grid">
        <div v-for="i in 6" :key="i" class="skeleton" style="height: 230px" />
      </div>
      <div v-else-if="error" class="empty bento-card"><p>Postlarni yuklab bo'lmadi.</p></div>
      <div v-else-if="!filtered.length" class="empty bento-card"><p>Bu rubrikada post yo'q.</p></div>
      <div v-else class="grid">
        <PostCard v-for="(p, i) in filtered" :key="p.run_id" :post="p" :index="i" />
      </div>
    </section>
  </div>
</template>

<style scoped>
.page { padding-top: 40px; }

/* HERO BENTO */
.hero-bento { display: grid; grid-template-columns: 1.08fr 0.92fr; gap: 20px; margin-bottom: 20px; }
.hero-card { padding: 44px; display: flex; flex-direction: column; }
.eyebrow { display: inline-block; align-self: flex-start; padding: 8px 15px; border-radius: 999px; font-size: 0.82rem; font-weight: 600; color: var(--text-dim); background: var(--glass); border: 1px solid var(--glass-border); margin-bottom: 22px; }
.hh { font-size: clamp(2.2rem, 4.4vw, 3.5rem); font-weight: 800; margin-bottom: 18px; }
.sub { color: var(--text-dim); font-size: 1.05rem; max-width: 500px; margin-bottom: 28px; }
.cta-row { display: flex; align-items: center; gap: 12px; margin-bottom: auto; }
.hero-foot { display: flex; align-items: center; gap: 14px; margin-top: 40px; padding-top: 26px; border-top: 1px solid rgba(255,255,255,0.08); }
.avatars { display: flex; }
.ava { width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center; font-size: 1.1rem; border: 1px solid; margin-left: -12px; backdrop-filter: blur(6px); }
.ava:first-child { margin-left: 0; }
.foot-txt { display: flex; flex-direction: column; }
.foot-txt b { font-weight: 700; font-size: 0.98rem; }
.foot-txt span { color: var(--text-faint); font-size: 0.85rem; }

/* FEATURE CARD */
.feature-card { padding: 34px; display: flex; flex-direction: column; transition: transform 0.25s, border-color 0.25s; }
.feature-card:hover { transform: translateY(-4px); border-color: var(--glass-border-strong); }
.f-glow { position: absolute; top: -20%; right: -15%; width: 340px; height: 340px; border-radius: 50%; background: radial-gradient(circle, var(--rc), transparent 65%); opacity: 0.32; filter: blur(30px); }
.f-top { display: flex; align-items: center; justify-content: space-between; position: relative; }
.f-tag { font-size: 0.78rem; font-weight: 700; color: var(--rc); }
.f-title { position: relative; font-size: clamp(1.5rem, 2.6vw, 2.15rem); font-weight: 800; margin: 22px 0 14px; }
.f-lead { position: relative; color: var(--text-dim); font-size: 1.02rem; margin-bottom: 22px; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
.f-cta { position: relative; display: flex; align-items: center; justify-content: space-between; font-weight: 700; color: var(--text); margin-top: auto; }
.sm-circle { width: 44px; height: 44px; }

/* BENTO 3 */
.bento-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 20px; }
.card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.card-head h3, .promo-card h3, .stat-card h3 { font-size: 1.25rem; font-weight: 700; }
.muted { color: var(--text-faint); font-size: 0.85rem; }
.list-card { padding: 26px; }
.rlist { display: flex; flex-direction: column; gap: 6px; }
.ritem { display: flex; align-items: center; gap: 12px; padding: 9px 10px; border-radius: 14px; background: transparent; border: 0; cursor: pointer; transition: background 0.15s; text-align: left; }
.ritem:hover { background: var(--glass); }
.remoji { width: 38px; height: 38px; border-radius: 11px; display: grid; place-items: center; font-size: 1.1rem; flex: none; }
.rname { flex: 1; color: var(--text); font-weight: 600; font-size: 0.95rem; }
.rcount { color: var(--text-faint); font-size: 0.85rem; font-weight: 600; }

.promo-card { padding: 30px; display: flex; flex-direction: column; }
.p-glow { position: absolute; bottom: -30%; left: -10%; width: 280px; height: 280px; border-radius: 50%; background: radial-gradient(circle, var(--a1), transparent 65%); opacity: 0.22; filter: blur(28px); }
.p-badge { position: relative; align-self: flex-start; padding: 6px 13px; border-radius: 999px; font-size: 0.78rem; font-weight: 700; color: #04121a; background: var(--accent-grad); margin-bottom: 18px; }
.promo-card h3 { position: relative; margin-bottom: 10px; line-height: 1.2; }
.promo-card p { position: relative; color: var(--text-dim); font-size: 0.95rem; margin-bottom: 22px; flex: 1; }
.promo-card .btn { position: relative; align-self: flex-start; }

.stat-card { padding: 30px; }
.stat-card h3 { margin-bottom: 20px; }
.stat-grid { display: flex; flex-direction: column; gap: 14px; }
.s { display: flex; align-items: baseline; gap: 12px; }
.s b { font-family: var(--font-head); font-size: 1.9rem; font-weight: 800; min-width: 90px; }
.s span { color: var(--text-faint); font-weight: 600; }

/* FEED */
.feed { padding-top: 34px; }
.feed-head { display: flex; align-items: center; justify-content: space-between; gap: 20px; flex-wrap: wrap; margin-bottom: 24px; }
.feed-head h2 { font-size: 1.7rem; font-weight: 700; }
.filters { display: flex; gap: 8px; flex-wrap: wrap; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
.empty { padding: 50px; text-align: center; color: var(--text-dim); }

@media (max-width: 900px) {
  .hero-bento { grid-template-columns: 1fr; }
  .bento-3 { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .hero-card, .feature-card { padding: 28px; }
}
</style>
