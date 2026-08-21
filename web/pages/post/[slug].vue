<script setup lang="ts">
import type { SitePostDetail } from '~/composables/useApi'

const route = useRoute()
const slug = route.params.slug as string
const { meta } = useRubrics()

const { data: post, error } = await useAsyncData<SitePostDetail>(
  `post-${slug}`,
  () => $fetch(apiUrl(`/api/site/posts/${slug}`)),
)

if (!post.value && !error.value) {
  // topilmadi
}

const r = computed(() => meta(post.value?.rubric))
const dateLabel = computed(() => uzDate(post.value?.published_at, true))

useHead(() => ({ title: post.value ? `${post.value.title} — Move Space` : 'Post — Move Space' }))

// Ro'yxatga o'xshash qatorlarni bullet qilib ko'rsatish
function isListItem(s: string): boolean {
  return /^\s*(\d+[.)]|[-•])\s/.test(s)
}
</script>

<template>
  <article v-if="post" class="wrap container">
    <NuxtLink to="/" class="back">← Barcha postlar</NuxtLink>

    <div class="head rise">
      <span class="badge" :style="{ color: r.color, borderColor: r.color + '55' }">
        {{ r.emoji }} {{ r.label }}
      </span>
      <h1 class="title">{{ post.title }}</h1>
      <div class="meta">
        <span>{{ dateLabel }}</span>
        <span class="sep">·</span>
        <span>{{ post.reading_minutes }} daqiqa o'qish</span>
      </div>
    </div>

    <div class="body glass rise" :style="{ '--rc': r.color }">
      <div class="b-glow" />
      <p v-if="post.lead" class="lead">{{ post.lead }}</p>

      <template v-for="(block, i) in post.body" :key="i">
        <p v-if="!isListItem(block)" class="para">{{ block }}</p>
        <p v-else class="li">{{ block }}</p>
      </template>

      <div v-if="post.takeaway" class="callout">
        <span class="c-ic">💡</span>
        <p>{{ post.takeaway }}</p>
      </div>

      <p v-if="post.cta" class="cta-line">{{ post.cta }}</p>

      <div v-if="post.tags?.length" class="tags">
        <span v-for="t in post.tags" :key="t" class="tag">#{{ t }}</span>
      </div>
    </div>

    <div class="foot-cta glass">
      <div>
        <h3>Yana ko'proq o'qing</h3>
        <p>Har hafta yangi postlar — Telegram kanalda birinchi bo'lib oling.</p>
      </div>
      <a href="https://t.me" target="_blank" class="btn btn-primary">Kanalga obuna</a>
    </div>
  </article>

  <div v-else class="wrap container notfound">
    <div class="glass nf">
      <h1>😕 Post topilmadi</h1>
      <p>Bu sahifa mavjud emas yoki o'chirilgan.</p>
      <NuxtLink to="/" class="btn btn-primary">Bosh sahifaga</NuxtLink>
    </div>
  </div>
</template>

<style scoped>
.wrap { padding: 40px 22px 0; max-width: 820px; }
.back { display: inline-block; color: var(--text-dim); font-weight: 600; margin-bottom: 28px; transition: color 0.15s; }
.back:hover { color: var(--a2); }
.head { margin-bottom: 26px; }
.title { font-size: clamp(1.9rem, 5vw, 3rem); font-weight: 800; margin: 16px 0 16px; }
.meta { color: var(--text-faint); font-size: 0.95rem; display: flex; gap: 10px; align-items: center; }
.sep { opacity: 0.5; }

.body { position: relative; padding: 44px; overflow: hidden; }
.b-glow { position: absolute; top: -20%; left: -10%; width: 320px; height: 320px; border-radius: 50%; background: radial-gradient(circle, var(--rc), transparent 65%); opacity: 0.18; filter: blur(34px); pointer-events: none; }
.lead { font-size: 1.28rem; font-weight: 600; color: var(--text); margin-bottom: 24px; line-height: 1.5; position: relative; }
.para { font-size: 1.08rem; color: var(--text-dim); margin-bottom: 18px; position: relative; }
.li { font-size: 1.06rem; color: var(--text-dim); margin: 6px 0 6px 6px; padding-left: 14px; border-left: 2px solid var(--rc); position: relative; }
.callout { display: flex; gap: 14px; align-items: flex-start; margin: 28px 0; padding: 20px 22px; border-radius: var(--radius-sm); background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border); position: relative; }
.callout .c-ic { font-size: 1.4rem; }
.callout p { color: var(--text); font-size: 1.02rem; }
.cta-line { font-style: italic; color: var(--a2); font-size: 1.1rem; margin-top: 24px; font-weight: 600; position: relative; }
.tags { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 28px; position: relative; }
.tag { font-size: 0.85rem; color: var(--text-dim); background: var(--glass); border: 1px solid var(--glass-border); padding: 5px 12px; border-radius: 999px; }

.foot-cta { margin-top: 30px; padding: 30px 34px; display: flex; align-items: center; justify-content: space-between; gap: 20px; flex-wrap: wrap; }
.foot-cta h3 { font-size: 1.3rem; margin-bottom: 4px; }
.foot-cta p { color: var(--text-dim); font-size: 0.95rem; }

.notfound { display: grid; place-items: center; min-height: 60vh; }
.nf { padding: 50px; text-align: center; }
.nf h1 { margin-bottom: 12px; }
.nf p { color: var(--text-dim); margin-bottom: 24px; }

@media (max-width: 720px) {
  .body { padding: 28px; }
}
</style>
