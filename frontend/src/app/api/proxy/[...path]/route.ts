// Backend-for-frontend proxy.
// The browser only ever talks to this Next.js server; this handler forwards to the RegLens API
// and adds the secret API key on the server side, so the key never reaches the browser.
// Responses are streamed through untouched, which is what lets answers arrive token by token.
import { connection, type NextRequest } from "next/server";

const API_URL = () => process.env.API_URL ?? "http://localhost:8000";
// Only these API areas may be reached through the proxy.
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

async function forward(req: NextRequest, ctx: RouteContext<"/api/proxy/[...path]">, method: Method) {
  await connection(); // always run at request time, never cached
  const { path } = await ctx.params;
  const joined = path.join("/");
  if (joined.includes("..") || !ALLOWED_PREFIXES.some((p) => joined.startsWith(p))) {
    return Response.json({ detail: "not found" }, { status: 404 });
  }
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (process.env.API_KEY) headers["X-API-Key"] = process.env.API_KEY;
  const accept = req.headers.get("accept");
  if (accept) headers["Accept"] = accept;

  let upstream: Response;
  try {
    upstream = await fetch(`${API_URL()}/${joined}${req.nextUrl.search}`, {
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
