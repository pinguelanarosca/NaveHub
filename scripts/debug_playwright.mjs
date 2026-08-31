import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.goto(process.argv[2] ?? "about:blank");
console.log(await page.title());
await browser.close();

