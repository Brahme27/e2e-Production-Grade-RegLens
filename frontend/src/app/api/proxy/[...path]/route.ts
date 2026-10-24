// Backend-for-frontend proxy.
// The browser only ever talks to this Next.js server; this handler forwards to the RegLens API
// and adds the secret API key on the server side, so the key never reaches the browser.
// Responses are streamed through untouched, which is what lets answers arrive token by token.
import { connection, type NextRequest } from "next/server";

const API_URL = () => process.env.API_URL ?? "http://localhost:8000";
// Only these API areas may be reached through the proxy (matched on whole path segments).
const ALLOWED_PREFIXES = [
  "v1/ask",
  "v1/feedback",
  "v1/documents",
  "v1/graph",
  "v1/changes",
  "v1/impact",
  "v1/obligations",
  "v1/gaps",
  "v1/meta",
  "v1/entities",
  "v1/reports",
];

type Method = "GET" | "POST" | "PATCH";

const notFound = () => Response.json({ detail: "not found" }, { status: 404 });

// Segments arrive URL-decoded, so "%2e%2e" is already "..". Anything that could change the path
// once re-encoded (dot segments, slashes, a leftover "%" from double encoding) is refused.
function safePath(segments: string[]): string | null {
  const bad = segments.some(
    (s) => s === "" || s === "." || s === ".." || /[\\/%]/.test(s),
  );
  if (bad) return null;
  const joined = segments.join("/");
  const allowed = ALLOWED_PREFIXES.some((p) => joined === p || joined.startsWith(`${p}/`));
  return allowed ? segments.map(encodeURIComponent).join("/") : null;
}

// Writes must come from this console's own pages (blocks cross-site form posts) and be JSON.
function writeAllowed(req: NextRequest): boolean {
  const origin = req.headers.get("origin");
  if (origin && origin !== req.nextUrl.origin) {
    const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host");
    if (!host || new URL(origin).host !== host) return false;
  }
  const type = req.headers.get("content-type") ?? "";
  return type.split(";")[0].trim().toLowerCase() === "application/json";
}

// The client's address for the API's rate limiter: the rightmost forwarded hop is the one
// written by our own load balancer; anything to its left is what the browser claimed.
function clientAddress(req: NextRequest): string | null {
  const hops = (req.headers.get("x-forwarded-for") ?? "")
    .split(",")
    .map((h) => h.trim())
    .filter(Boolean);
  return hops.at(-1) ?? req.headers.get("x-real-ip");
}

async function forward(req: NextRequest, ctx: RouteContext<"/api/proxy/[...path]">, method: Method) {
  await connection(); // always run at request time, never cached
  const { path } = await ctx.params;
  const target = safePath(path);
  if (!target) return notFound();
  if (method !== "GET" && !writeAllowed(req)) {
    return Response.json({ detail: "cross-origin or non-JSON write refused" }, { status: 403 });
  }
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (process.env.API_KEY) headers["X-API-Key"] = process.env.API_KEY;
  const accept = req.headers.get("accept");
  if (accept) headers["Accept"] = accept;
  const client = clientAddress(req);
  if (client) headers["X-Forwarded-For"] = client;

  let upstream: Response;
  try {
    upstream = await fetch(`${API_URL()}/${target}${req.nextUrl.search}`, {
      method,
      headers,
      body: method === "GET" ? undefined : await req.text(),
      cache: "no-store",
    });
  } catch {
    return Response.json({ detail: "RegLens API is unreachable" }, { status: 502 });
  }
  const passthrough: Record<string, string> = {
    "content-type": upstream.headers.get("content-type") ?? "application/octet-stream",
    "cache-control": "no-store",
  };
  const disposition = upstream.headers.get("content-disposition");
  if (disposition) passthrough["content-disposition"] = disposition;
  return new Response(upstream.body, { status: upstream.status, headers: passthrough });
}

export async function GET(req: NextRequest, ctx: RouteContext<"/api/proxy/[...path]">) {
  return forward(req, ctx, "GET");
}

export async function POST(req: NextRequest, ctx: RouteContext<"/api/proxy/[...path]">) {
  return forward(req, ctx, "POST");
}

export async function PATCH(req: NextRequest, ctx: RouteContext<"/api/proxy/[...path]">) {
  return forward(req, ctx, "PATCH");
}
