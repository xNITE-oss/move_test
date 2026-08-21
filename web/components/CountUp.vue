<script setup lang="ts">
// Sonni 0 dan berilgan qiymatgacha sanaydi (ko'rinishga kirganda).
const props = withDefaults(
  defineProps<{
    to: number
    suffix?: string
    prefix?: string
    duration?: number
    decimals?: number
  }>(),
  { suffix: '', prefix: '', duration: 1700, decimals: 0 },
)

// SSR — darrov yakuniy qiymat (SEO/no-flash); brauzer 0 dan animatsiya qiladi.
const value = ref(import.meta.server ? props.to : 0)
const el = ref<HTMLElement | null>(null)
let done = false

function run() {
  if (done) return
  done = true
  const start = performance.now()
  const step = (now: number) => {
    const t = Math.min(1, (now - start) / props.duration)
    const eased = 1 - Math.pow(1 - t, 3) // easeOutCubic
    value.value = props.to * eased
    if (t < 1) requestAnimationFrame(step)
    else value.value = props.to
  }
  requestAnimationFrame(step)
}

onMounted(() => {
  value.value = 0
  if (typeof IntersectionObserver === 'undefined') return run()
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          run()
          io.disconnect()
        }
      }
    },
    { threshold: 0.4 },
  )
  if (el.value) io.observe(el.value)
})

const text = computed(
  () => props.prefix + value.value.toFixed(props.decimals) + props.suffix,
)
</script>

<template>
  <span ref="el">{{ text }}</span>
</template>
