// Rubrika kaliti -> ko'rinish (nom, emoji, rang). Sayt API faqat kalitni
// qaytaradi; chiroyli badge uchun shu jadval ishlatiladi.
export interface RubricMeta {
  label: string
  emoji: string
  color: string
}

const MAP: Record<string, RubricMeta> = {
  active_life: { label: 'Active Life', emoji: '👟', color: '#34d399' },
  camping: { label: 'Camping', emoji: '🏕️', color: '#f59e0b' },
  cycling: { label: 'Cycling', emoji: '🚴', color: '#22d3ee' },
  hiking: { label: 'Hiking', emoji: '⛰️', color: '#818cf8' },
  move_uz: { label: 'Move UZ', emoji: '🇺🇿', color: '#f472b6' },
  race: { label: 'Poyga', emoji: '🏁', color: '#fb7185' },
  running: { label: 'Yugurish', emoji: '🏃', color: '#2dd4bf' },
}

export function useRubrics() {
  const meta = (key?: string | null): RubricMeta =>
    (key && MAP[key]) || { label: key || 'Post', emoji: '✨', color: '#94a3b8' }
  return { meta, all: MAP }
}
