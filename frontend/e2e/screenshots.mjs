// Captures the README screenshots from a running stack: node e2e/screenshots.mjs
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const OUT = "../docs/screenshots";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });

await page.goto(`${BASE}/`);
await page.getByTestId("question").fill("What must a bank's board approve before outsourcing a material activity under RBI rules?");
await page.getByTestId("ask").click();
const chip = page.getByTestId("answer").getByRole("button", { name: /Show source/ }).first();
await chip.waitFor({ timeout: 120_000 });
await chip.click();
await page.getByText("Open in document").waitFor();
await page.waitForTimeout(800);
await page.screenshot({ path: `${OUT}/ask.png`, fullPage: true });

await page.goto(`${BASE}/impact`);
await page.getByTestId("impact-target").selectOption("pra-outsourcing@asof2026-10-24");
await page.getByTestId("impact-start").click();
await page.getByTestId("impact-status").waitFor({ timeout: 600_000 });
await page.waitForTimeout(1500);
await page.screenshot({ path: `${OUT}/impact.png`, fullPage: true });

await page.goto(`${BASE}/evaluation`);
await page.waitForTimeout(2500);
await page.screenshot({ path: `${OUT}/evaluation.png`, fullPage: true });

await page.goto(`${BASE}/documents`);
await page.waitForTimeout(2000);
await page.screenshot({ path: `${OUT}/documents.png`, fullPage: true });

await browser.close();
console.log("screenshots written to docs/screenshots");
