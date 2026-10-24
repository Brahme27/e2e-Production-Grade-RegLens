# 03: The proxy (backend-for-frontend)

**File:** `frontend/src/app/api/proxy/[...path]/route.ts`

## What
The browser never calls the RegLens API directly. It calls `/api/proxy/v1/...` on the
console's own server, which:
1. checks the path against an **allow-list** (`v1/ask`, `v1/documents`, …) and rejects `..`;
2. adds the secret `X-API-Key` header **on the server**;
3. forwards the request and **streams the response straight back** without buffering it, so
   answer tokens arrive as they are generated.

## Why
- **The API key never reaches the browser.** Anything sent to a browser can be read by
  its user. A key embedded in JavaScript is a published key.
- **One origin.** The browser talks to one site, so there are no CORS problems, and the
  API can stay on a private network (on AWS it's reachable only inside the VPC; the console
  reaches it through Cloud Map DNS).
- **Less attack surface.** Only the allow-listed API areas are reachable from outside.

**Analogy:** a receptionist who carries your request to the back office using a staff badge.
You never get the badge, and you can only ask for things on the reception's menu.
