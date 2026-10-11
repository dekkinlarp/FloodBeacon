// Canonicalizes floodbeacon.tech page requests (www and plain HTTP) to https://floodbeacon.tech.
// workers.dev and Preview hosts are served as-is so PR previews stay on their own URL.
// Only navigations reach this script (see run_worker_first in wrangler.jsonc).
const CANONICAL_HOST = 'floodbeacon.tech';

interface Env {
  ASSETS: { fetch(request: Request): Promise<Response> };
  /** "off" in local preview, where wrangler dev presents requests as http://floodbeacon.tech. */
  CANONICAL_REDIRECTS?: string;
}

export default {
  fetch(request: Request, env: Env): Promise<Response> | Response {
    const url = new URL(request.url);
    const ownDomain = url.hostname === CANONICAL_HOST || url.hostname.endsWith(`.${CANONICAL_HOST}`);
    if (env.CANONICAL_REDIRECTS !== 'off' && ownDomain && (url.protocol !== 'https:' || url.hostname !== CANONICAL_HOST)) {
      url.protocol = 'https:';
      url.hostname = CANONICAL_HOST;
      url.port = '';
      return Response.redirect(url.toString(), 301);
    }
    return env.ASSETS.fetch(request);
  },
};
