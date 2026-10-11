import { createContext, useContext, useState, type ReactNode } from 'react';
import { DEFAULT_SITE, SITES, type SiteId } from '../data/sites';

const SiteContext = createContext<{ siteId: SiteId; selectSite: (id: SiteId) => void } | null>(null);

export function SiteProvider({ children }: { children: ReactNode }) {
  const [siteId, selectSite] = useState<SiteId>(DEFAULT_SITE);
  return <SiteContext.Provider value={{ siteId, selectSite }}>{children}</SiteContext.Provider>;
}

export function useSite() {
  const context = useContext(SiteContext);
  if (!context) throw new Error('SiteProvider is required');
  return { ...context, site: SITES[context.siteId] };
}
