// v-reveal — element ko'rinishga kirganda "in" klassini qo'shadi (bir marta).
// Universal plugin: direktiva SSR'da ham ro'yxatdan o'tadi (warning bo'lmaydi),
// lekin IntersectionObserver faqat brauzerda ishlaydi.
export default defineNuxtPlugin((nuxtApp) => {
  const io =
    import.meta.client && typeof IntersectionObserver !== 'undefined'
      ? new IntersectionObserver(
          (entries) => {
            for (const e of entries) {
              if (e.isIntersecting) {
                e.target.classList.add('in')
                io!.unobserve(e.target)
              }
            }
          },
          { threshold: 0.14, rootMargin: '0px 0px -8% 0px' },
        )
      : null

  nuxtApp.vueApp.directive('reveal', {
    mounted(el: HTMLElement, binding) {
      el.classList.add('reveal')
      if (binding.value != null) el.style.transitionDelay = `${binding.value}ms`
      if (io) io.observe(el)
      else el.classList.add('in')
    },
    unmounted(el: HTMLElement) {
      if (io) io.unobserve(el)
    },
  })
})
