<script setup lang="ts">
import type { SitePost } from '~/composables/useApi'

const props = defineProps<{ post: SitePost; index?: number }>()
const { meta } = useRubrics()
const r = computed(() => meta(props.post.rubric))

const dateLabel = computed(() => uzDate(props.post.published_at))
</script>

<template>
  <NuxtLink
    :to="`/post/${post.slug}`"
    class="card glass rise"
    :style="{ animationDelay: `${(index || 0) * 60}ms`, '--rc': r.color }"
  >
    <div class="glow" />
    <div class="top">
      <span class="badge" :style="{ color: r.color, borderColor: r.color + '55' }">
        {{ r.emoji }} {{ r.label }}
      </span>
      <span class="rt">{{ post.reading_minutes }} daq</span>
    </div>

    <h3 class="title">{{ post.title }}</h3>
    <p class="lead">{{ post.lead }}</p>

    <div class="foot">
      <span class="date">{{ dateLabel }}</span>
      <span class="read">O'qish
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </span>
    </div>
  </NuxtLink>
</template>

<style scoped>
.card {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 24px;
  overflow: hidden;
  transition: transform 0.25s cubic-bezier(0.22,1,0.36,1), border-color 0.25s;
  min-height: 220px;
}
.card:hover { transform: translateY(-6px); border-color: var(--glass-border-strong); }
.card:hover .glow { opacity: 0.9; }
.glow {
  position: absolute; top: -40%; right: -30%;
  width: 220px; height: 220px; border-radius: 50%;
  background: radial-gradient(circle, var(--rc), transparent 65%);
  opacity: 0.35; filter: blur(20px);
  transition: opacity 0.3s; pointer-events: none;
}
.top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.rt { font-size: 0.8rem; color: var(--text-faint); font-weight: 600; }
.title {
  font-size: 1.24rem; font-weight: 700; margin-bottom: 10px;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.lead {
  color: var(--text-dim); font-size: 0.96rem; flex: 1;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.foot { display: flex; align-items: center; justify-content: space-between; margin-top: 18px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.07); }
.date { font-size: 0.85rem; color: var(--text-faint); }
.read { display: inline-flex; align-items: center; gap: 6px; font-weight: 700; font-size: 0.9rem; color: var(--rc); }
</style>
