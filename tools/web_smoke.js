#!/usr/bin/env node
// Смок веб-версии (р.24): настоящий Chromium (Playwright) против dist/web/.
//
// Что доказывает: страница грузится без ошибок и алертов; кнопка «Играть»
// открывается только по сигналу игры (BJ2 READY); канвас подгоняется под окно;
// новая партия начинается, предмет берётся, и автосейв переживает ЗАКРЫТИЕ
// БРАУЗЕРА без beforeunload (профиль на диске, второй запуск) — «Продолжить»
// ведёт в комнату, а не в настройки. Без своей синхронизации в index.html
// сейв здесь терялся: рантайм пишет IndexedDB только по beforeunload.
// Кадры кладутся в work/web_shots/ — смотреть глазами (урок №7, LESSONS.md).
//
// Запуск (нужны Node и Playwright с Chromium; в облачном контейнере они есть):
//   python3 tools/build_web.py --serve 8000 &      # или любой статический сервер
//   NODE_PATH=$(npm root -g) node tools/web_smoke.js http://127.0.0.1:8000/
const { chromium } = require("playwright");
const fs = require("fs");

const URL_ = process.argv[2] || "http://127.0.0.1:8000/";
const OUT = "work/web_shots";
const VW = 1280, VH = 800;                         // не 16:9 — letterbox в деле
const S = Math.min(VW / 1920, VH / 1080), OX = (VW - 1920 * S) / 2, OY = (VH - 1080 * S) / 2;
const W = (x, y) => [OX + x * S, OY + y * S];      // мир 1920×1080 → окно
const fails = [];
const check = (ok, msg) => { console.log((ok ? "[OK  ] " : "[FAIL] ") + msg); if (!ok) fails.push(msg); };

async function brightness(page, x0, y0, x1, y1) {
  // средняя яркость прямоугольника мира по скриншоту окна (0..1)
  const [ax, ay] = W(x0, y0), [bx, by] = W(x1, y1);
  const png = await page.screenshot({ clip: { x: ax, y: ay, width: bx - ax, height: by - ay } });
  return await page.evaluate(async (b64) => {
    const img = new Image(); img.src = "data:image/png;base64," + b64; await img.decode();
    const c = document.createElement("canvas"); c.width = img.width; c.height = img.height;
    const g = c.getContext("2d"); g.drawImage(img, 0, 0);
    const d = g.getImageData(0, 0, c.width, c.height).data;
    let s = 0; for (let i = 0; i < d.length; i += 4) s += d[i] + d[i + 1] + d[i + 2];
    return s / (d.length / 4) / 765;
  }, png.toString("base64"));
}

async function clickW(page, x, y, n = 1, pause = 250) {
  for (let i = 0; i < n; i++) { const [sx, sy] = W(x, y); await page.mouse.click(sx, sy); await page.waitForTimeout(pause); }
}

async function boot(page, tag) {
  await page.goto(URL_, { waitUntil: "load" });
  await page.waitForSelector("#play:not([disabled])", { timeout: 180000 });
  await page.screenshot({ path: `${OUT}/${tag}_overlay.png` });
  await page.click("#play");
  await page.waitForTimeout(1500);
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const profile = fs.mkdtempSync(require("os").tmpdir() + "/bj2_web_profile_");
  const launch = () => chromium.launchPersistentContext(profile, {
    viewport: { width: VW, height: VH },
    args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
           "--autoplay-policy=no-user-gesture-required"] });
  const errors = [], dialogs = [];
  const watch = (page) => {
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    page.on("dialog", async (d) => { dialogs.push(d.message()); await d.dismiss(); });
  };

  // ---- запуск 1: чистый профиль, новая партия ----
  let ctx = await launch();
  let page = ctx.pages()[0] || await ctx.newPage();
  watch(page);
  const t0 = Date.now();
  await boot(page, "web_01");
  check(true, `загрузка до «Играть»: ${((Date.now() - t0) / 1000).toFixed(1)} с`);
  const cv = await page.evaluate(() => { const c = document.getElementById("canvas"); return [c.width, c.height]; });
  check(cv[0] === VW && cv[1] === VH, `канвас под окно: ${cv[0]}×${cv[1]}`);
  const overlayHidden = await page.evaluate(() => document.getElementById("overlay").classList.contains("hidden"));
  check(overlayHidden, "заставка скрыта после «Играть»");
  await page.screenshot({ path: `${OUT}/web_02_title.png` });
  check(await brightness(page, 0, 0, 1920, 1080) > 0.05, "титул нарисован (кадр не чёрный)");

  await clickW(page, 960, 596);                     // «НАЧАТЬ»
  await page.waitForTimeout(1500);
  await clickW(page, 1200, 900, 24, 200);           // пролистать вступление
  await page.waitForTimeout(800);
  await clickW(page, 1238 + 48, 706 + 31);          // линейка на столе
  await page.waitForTimeout(800);
  await clickW(page, 1200, 900, 6, 200);            // реплика о линейке
  await page.screenshot({ path: `${OUT}/web_03_room.png` });

  await page.setViewportSize({ width: 1600, height: 900 });   // ресайз окна
  await page.waitForTimeout(800);
  const cv2 = await page.evaluate(() => { const c = document.getElementById("canvas"); return [c.width, c.height]; });
  check(cv2[0] === 1600 && cv2[1] === 900, `канвас после ресайза: ${cv2[0]}×${cv2[1]}`);
  await page.setViewportSize({ width: VW, height: VH });
  await page.waitForTimeout(4000);                  // автосейв (3 с) + синхронизация (3 с)
  await ctx.close();                                // закрытие БЕЗ beforeunload

  // ---- запуск 2: тот же профиль — сейв обязан дожить ----
  ctx = await launch();
  page = ctx.pages()[0] || await ctx.newPage();
  watch(page);
  await boot(page, "web_04");
  await clickW(page, 960, 688);                     // «ПРОДОЛЖИТЬ» (вторая кнопка)
  await page.waitForTimeout(1500);
  await clickW(page, 1200, 900, 4, 200);
  await page.screenshot({ path: `${OUT}/web_05_continue.png` });
  // без сейва на этом месте «НАСТРОЙКИ», и центр кадра закрыла бы тёмная панель
  const mid = await brightness(page, 700, 300, 1200, 700);
  check(mid > 0.2, `сейв пережил закрытие браузера: «Продолжить» привело в комнату (яркость центра ${mid.toFixed(2)})`);

  check(errors.length === 0, `ошибок в консоли/странице: ${errors.length}` + (errors.length ? " — " + errors.slice(0, 3).join(" | ") : ""));
  check(dialogs.length === 0, `алертов: ${dialogs.length}` + (dialogs.length ? " — " + dialogs.join(" | ") : ""));
  await ctx.close();
  fs.rmSync(profile, { recursive: true, force: true });
  console.log(fails.length ? `WEB SMOKE FAIL (${fails.length})` : "WEB SMOKE PASS");
  process.exit(fails.length ? 1 : 0);
})().catch((e) => { console.error(e); console.log("WEB SMOKE FAIL"); process.exit(1); });
