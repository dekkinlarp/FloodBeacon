export const SITES = {
  'ahr-2021': { name: 'Ahr Valley', center: [7.03622715, 50.5141039], zoom: 16 },
  'derna-2023': { name: 'Derna', center: [22.6422, 32.7631], zoom: 16 },
  'nepal-2026': { name: 'Syabrubesi, Nepal', center: [85.341, 28.1649], zoom: 16 },
} as const;
export type SiteId = keyof typeof SITES;
export const DEFAULT_SITE: SiteId = 'ahr-2021';
