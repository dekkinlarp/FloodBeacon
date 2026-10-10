/** Screens reachable by URL hash. No router dependency. */
export type Route = { page: 'dispatch' } | { page: 'team'; teamId: string };

/** `#/team/TEAM-02` → team view; anything else → dispatch. */
export function parseRoute(hash: string): Route {
  const m = /^#\/team\/([A-Za-z0-9_-]+)\/?$/.exec(hash);
  return m ? { page: 'team', teamId: decodeURIComponent(m[1]!) } : { page: 'dispatch' };
}

export function teamViewHref(teamId: string): string {
  return `#/team/${encodeURIComponent(teamId)}`;
}
