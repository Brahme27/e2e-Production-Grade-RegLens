# 02: The console

**Folder:** `frontend/` (Next.js 16, React 19, Tailwind 4)

## Pages
| Page | What a compliance officer does there |
|---|---|
| **Ask** (`/`) | Types a question, optionally picks an "as of" date and regulators; the answer streams in; each `[n]` marker is clickable and opens the paragraph, its status and validity window, with links to the document viewer and the regulator's site; 👍/👎 feedback |
| **Documents** | Every indexed document with status (current / superseded / future) and validity; the document page shows all versions, the supersession links, the text with the cited paragraph highlighted, and a red/green word-level diff between any two versions |
| **Change feed** | What came into force, what is scheduled, what stopped applying, since a date |
| **Impact board** | Pick a new rule → run the analysis → review each obligation's gap verdict (agree / override) → approve → download tickets |
| **Evaluation** | The ablation table and the answer, router, supersession and impact metrics, read live from the reports |

## Design choices
- **Client components for live data**, server components only for routing params: the
  console is a dashboard over live API data, so there's nothing to pre-render.
- **Testable**: stable `data-testid`s for the Playwright end-to-end tests (`frontend/e2e/`).
- **Honest UI**: the impact board says the firms are fictional; every answer shows the
  "not legal advice" disclaimer and whether its citations passed verification.

**Analogy:** the dashboard of a car: it doesn't do the work, but it shows exactly what the
engine is doing and gives the driver the controls that matter.
