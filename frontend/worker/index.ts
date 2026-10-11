// Canonicalizes page requests to https://floodbeacon.tech; everything else is static assets.
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
    if (env.CANONICAL_REDIRECTS !== 'off' && (url.protocol !== 'https:' || url.hostname !== CANONICAL_HOST)) {
      url.protocol = 'https:';
      url.hostname = CANONICAL_HOST;
      url.port = '';
      return Response.redirect(url.toString(), 301);
    }
    return env.ASSETS.fetch(request);
  },
};
