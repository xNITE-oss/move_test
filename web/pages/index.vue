<script setup lang="ts">
import type { SitePost } from '~/composables/useApi'

const { meta } = useRubrics()

const { data, pending, error } = await useAsyncData<SitePost[]>(
  'site-posts',
  () => $fetch(apiUrl('/api/site/posts?limit=60')),
  { default: () => [] },
)

const active = ref<string>('all')

const rubrics = computed(() => {
  const keys = new Set<string>()
  ;(data.value || []).forEach((p) => p.rubric && keys.add(p.rubric))
  return [...keys]
})

const filtered = computed(() => {
  const list = data.value || []
  return active.value === 'all' ? list : list.filter((p) => p.rubric === active.value)
})

const featured = computed(() => filtered.value[0])
const rest = computed(() => filtered.value.slice(1))
</script>

<template>
  <div>
    <!-- HERO -->
    <section class="hero container">
      <div class="hero-in rise">
        <span class="pill glass">✦ O'zbekistonda faol hayot media-kanali</span>
        <h1 class="hh">
          Harakat — bu <span class="grad-text">makon</span>.<br />
          Tabiat esa maydon.
        </h1>
        <p class="sub">
          Yugurish, hiking, velosiped va camping bo'yicha amaliy postlar —
          har biri tekshirilgan, aniq va O'zbekiston sharoitiga moslangan.
        </p>
        <div class="cta">
          <a href="#feed" class="btn btn-primary">Postlarni ko'rish
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M12 5v14M6 13l6 6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </a>
          <a href="https://t.me" target="_blank" class="btn btn-ghost">Telegram kanal</a>
        </div>

        <div class="stats">
          <div class="stat glass" v-reveal="100">
            <span class="num grad-text"><CountUp :to="(data || []).length" suffix="+" /></span>
            <span class="lbl">Post</span>
          </div>
          <div class="stat glass" v-reveal="200">
            <span class="num grad-text"><CountUp :to="rubrics.length || 7" /></span>
            <span class="lbl">Rubrika</span>
          </div>
          <div class="stat glass" v-reveal="300">
            <span class="num grad-text"><CountUp :to="100" suffix="%" /></span>
            <span class="lbl">Tekshirilgan</span>
          </div>
        </div>
      </div>
    </section>

    <!-- FEED -->
    <section id="feed" class="container feed">
      <div class="feed-head" v-reveal>
        <h2>So'nggi postlar</h2>
        <div class="filters">
          <button class="chip" :class="{ active: active === 'all' }" @click="active = 'all'">Hammasi</button>
          <button
            v-for="k in rubrics" :key="k"
            class="chip" :class="{ active: active === k }"
            @click="active = k"
          >{{ meta(k).emoji }} {{ meta(k).label }}</button>
        </div>
      </div>

      <!-- Yuklanmoqda -->
      <div v-if="pending" class="grid">
        <div v-for="i in 6" :key="i" class="skeleton" style="height: 220px" />
      </div>

      <!-- Xato -->
      <div v-else-if="error" class="empty glass">
        <p>Postlarni yuklab bo'lmadi. Keyinroq urinib ko'ring.</p>
      </div>

      <!-- Bo'sh -->
      <div v-else-if="!filtered.length" class="empty glass">
        <p>Hozircha bu rubrikada post yo'q.</p>
      </div>

      <!-- Kontent -->
      <template v-else>
        <NuxtLink
          v-if="featured"
          :to="`/post/${featured.slug}`"
          class="feature glass"
          v-reveal
          :style="{ '--rc': meta(featured.rubric).color }"
        >
          <div class="f-glow" />
          <span class="badge" :style="{ color: meta(featured.rubric).color, borderColor: meta(featured.rubric).color + '55' }">
            {{ meta(featured.rubric).emoji }} {{ meta(featured.rubric).label }} · Tavsiya
          </span>
          <h3 class="f-title">{{ featured.title }}</h3>
          <p class="f-lead">{{ featured.lead }}</p>
          <span class="f-read">O'qishni boshlash →</span>
        </NuxtLink>

        <div class="grid">
          <PostCard v-for="(p, i) in rest" :key="p.run_id" :post="p" :index="i" />
        </div>
      </template>
    </section>
  </div>
</template>

<style scoped>
/* HERO */
.hero { padding: 70px 22px 30px; }
.hero-in { max-width: 820px; }
.pill { display: inline-block; padding: 8px 16px; border-radius: 999px; font-size: 0.85rem; color: var(--text-dim); font-weight: 600; margin-bottom: 26px; }
.hh { font-size: clamp(2.4rem, 6vw, 4.2rem); font-weight: 800; margin-bottom: 22px; }
.sub { font-size: clamp(1rem, 2.2vw, 1.2rem); color: var(--text-dim); max-width: 620px; margin-bottom: 32px; }
.cta { display: flex; gap: 14px; flex-wrap: wrap; }
.stats { display: flex; gap: 16px; margin-top: 48px; flex-wrap: wrap; }
.stat { padding: 20px 26px; display: flex; flex-direction: column; gap: 4px; min-width: 130px; }
.num { font-family: var(--font-head); font-size: 2rem; font-weight: 800; }
.lbl { color: var(--text-faint); font-size: 0.88rem; font-weight: 600; }

/* FEED */
.feed { padding-top: 40px; }
.feed-head { display: flex; align-items: center; justify-content: space-between; gap: 20px; flex-wrap: wrap; margin-bottom: 26px; }
.feed-head h2 { font-size: 1.8rem; font-weight: 700; }
.filters { display: flex; gap: 9px; flex-wrap: wrap; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 22px; }
.empty { padding: 60px; text-align: center; color: var(--text-dim); }

/* Feature (katta) */
.feature { position: relative; display: block; padding: 40px; margin-bottom: 22px; overflow: hidden; transition: transform 0.25s, border-color 0.25s; }
.feature:hover { transform: translateY(-4px); border-color: var(--glass-border-strong); }
.f-glow { position: absolute; top: -30%; right: -10%; width: 380px; height: 380px; border-radius: 50%; background: radial-gradient(circle, var(--rc), transparent 65%); opacity: 0.3; filter: blur(30px); }
.f-title { font-size: clamp(1.6rem, 3.5vw, 2.4rem); font-weight: 800; margin: 16px 0 12px; max-width: 760px; position: relative; }
.f-lead { color: var(--text-dim); font-size: 1.08rem; max-width: 680px; margin-bottom: 20px; position: relative; }
.f-read { font-weight: 700; color: var(--rc); position: relative; }

@media (max-width: 720px) {
  .hero { padding: 44px 22px 20px; }
  .feature { padding: 26px; }
  .stat { min-width: 100px; padding: 16px 20px; }
}
</style>
