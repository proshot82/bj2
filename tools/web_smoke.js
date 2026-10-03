#!/usr/bin/env node
// Смок веб-версии (р.24): настоящий Chromium (Playwright) против dist/web/.
//
// Что доказывает: страница грузится без ошибок и алертов; кнопка «Играть»
// открывается только по сигналу игры (BJ2 READY); канвас подгоняется под окно;
// новая партия начинается, предмет берётся, и автосейв переживает ЗАКРЫТИЕ
// БРАУЗЕРА без beforeunload (профиль на диске, второй запуск) — «Продолжить»
// ведёт в комнату, а не в настройки. Без своей синхронизации в index.html
// сейв здесь терялся: рантайм пишет IndexedDB только по beforeunload.
// (р.25) Третий запуск — сенсорный экран: телефонная вкладка 915×412 с
// настоящими касаниями Chromium. Канвас обязан встать под вкладку (до р.25 он
// застревал на минимуме окна 960×540 — кадр сплющивался), тап обязан работать
// как ЛКМ (вход в зум), удержание — как ПКМ (выход из зума); страница вместо
// клавиш показывает памятку касаний.
// (р.26) Четвёртый запуск — телефон вертикально (412×915): игра получает флаг
// --touch и рисует кадр «лёжа»; тап по месту, где «НАЧАТЬ» стоит ТОЛЬКО в
// повёрнутом кадре, обязан начать партию. Пятый — «внутри Telegram»: адрес с
// параметрами запуска Mini App, SDK telegram.org подменён записывающей
// заглушкой; оболочка обязана попросить весь экран, отключить свайп-закрытие,
// зафиксировать горизонталь и отступить канвасом от кнопок Telegram.
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

async function shotDiff(page, a, b) {
  // средняя разница двух кадров окна (0..1): зум с комнатой не спутать
  return await page.evaluate(async ([a64, b64]) => {
    const load = async (s) => { const i = new Image(); i.src = "data:image/png;base64," + s; await i.decode(); return i; };
    const [ia, ib] = [await load(a64), await load(b64)];
    const px = (img) => { const c = document.createElement("canvas"); c.width = img.width; c.height = img.height;
      const g = c.getContext("2d"); g.drawImage(img, 0, 0); return g.getImageData(0, 0, c.width, c.height).data; };
    const [da, db] = [px(ia), px(ib)];
    let s = 0; for (let i = 0; i < da.length; i += 4) s += Math.abs(da[i] - db[i]) + Math.abs(da[i + 1] - db[i + 1]) + Math.abs(da[i + 2] - db[i + 2]);
    return s / (da.length / 4) / 765;
  }, [a.toString("base64"), b.toString("base64")]);
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
  const deskKeys = await page.evaluate(() => [!document.getElementById("keys-mouse").hidden,
                                              !document.getElementById("touchnote").hidden]);
  check(deskKeys[0] && !deskKeys[1], "компьютер: клавиши мыши, памятки касаний нет");
  const noTg = await page.evaluate(() => typeof window.Telegram === "undefined");
  check(noTg, "вне Telegram его SDK не грузится");
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

  await ctx.close();
  fs.rmSync(profile, { recursive: true, force: true });

  // ---- запуск 3 (р.25): сенсорный экран, палец без мыши и клавиатуры ----
  const TW = 915, TH = 412;                        // Pixel 7 в альбомной ориентации
  const TS = Math.min(TW / 1920, TH / 1080), TOX = (TW - 1920 * TS) / 2, TOY = (TH - 1080 * TS) / 2;
  const WT = (x, y) => [TOX + x * TS, TOY + y * TS];
  const browser = await chromium.launch({
    args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
           "--autoplay-policy=no-user-gesture-required"] });
  const tctx = await browser.newContext({ viewport: { width: TW, height: TH },
                                          hasTouch: true, isMobile: true, deviceScaleFactor: 2 });
  const tp = await tctx.newPage();
  watch(tp);
  await tp.goto(URL_, { waitUntil: "load" });
  await tp.waitForSelector("#play:not([disabled])", { timeout: 180000 });
  const tKeys = await tp.evaluate(() => [!document.getElementById("keys-touch").hidden,
                                         !document.getElementById("touchnote").hidden,
                                         !document.getElementById("keys-mouse").hidden]);
  check(tKeys[0] && tKeys[1] && !tKeys[2], "сенсорный экран: памятка касаний вместо клавиш мыши");
  await tp.screenshot({ path: `${OUT}/web_06_touch_overlay.png` });
  await tp.tap("#play");
  await tp.waitForTimeout(1500);
  const tcv = await tp.evaluate(() => { const c = document.getElementById("canvas"); return [c.width, c.height]; });
  check(tcv[0] === TW && tcv[1] === TH, `канвас под телефонную вкладку: ${tcv[0]}×${tcv[1]} (кадр не сплющен)`);
  // касания — настоящие события Chromium: touchStart … touchEnd через CDP
  const cdp = await tctx.newCDPSession(tp);
  const touchW = async (x, y, ms, during) => {
    const [sx, sy] = WT(x, y);
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: sx, y: sy }] });
    if (during) await during(); else await tp.waitForTimeout(ms);
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  };
  const tapW = async (x, y, n = 1, pause = 200) => {
    for (let i = 0; i < n; i++) { await touchW(x, y, 40); await tp.waitForTimeout(pause); }
  };
  await tapW(960, 596);                            // «НАЧАТЬ» — тапом
  await tp.waitForTimeout(1500);
  await tapW(1200, 900, 24);                       // вступление
  await tapW(1553, 457);                           // дверь: сперва осмотр (реплики)
  await tapW(1200, 900, 10);
  await tp.waitForTimeout(800);
  const room0 = await tp.screenshot();
  await tapW(1553, 457);                           // тап = ЛКМ: вход в зум двери
  await tp.waitForTimeout(1000);
  const zoom = await tp.screenshot({ path: `${OUT}/web_07_touch_zoom.png` });
  // удержание в пустом месте зума = ПКМ: выход; кадр с кольцом — посреди удержания
  await touchW(420, 1000, 0, async () => {
    await tp.waitForTimeout(330);
    await tp.screenshot({ path: `${OUT}/web_08_touch_ring.png` });
    await tp.waitForTimeout(450);
  });
  await tp.waitForTimeout(1000);
  const room1 = await tp.screenshot({ path: `${OUT}/web_09_touch_room.png` });
  const dZoom = await shotDiff(tp, room0, zoom), dBack = await shotDiff(tp, room0, room1);
  check(dZoom > 0.08, `тап = ЛКМ: вход в зум (кадр сменился на ${(dZoom * 100).toFixed(1)} %)`);
  check(dBack < dZoom / 3, `удержание = ПКМ: выход из зума (от комнаты ${(dBack * 100).toFixed(1)} %, от зума ${(dZoom * 100).toFixed(1)} %)`);
  await tctx.close();

  // ---- запуск 4 (р.26): телефон вертикально — кадр «лёжа» ----
  // Окно 412×915: игра (флаг --touch) рисует мир повёрнутым на 90° по часовой,
  // во всю длинную сторону. Точка «НАЧАТЬ» считается по повороту: экран
  // px = W − vy, py = vx, где (vx, vy) — точка кадра «лёжа» 915×412. Без
  // поворота эта же точка экрана — мир (860, 540), над кнопкой: мимо.
  const PW = 412, PH = 915;
  const PS = Math.min(PH / 1920, PW / 1080), POX = (PH - 1920 * PS) / 2, POY = (PW - 1080 * PS) / 2;
  const WP = (x, y) => [PW - (POY + y * PS), POX + x * PS];
  const pctx = await browser.newContext({ viewport: { width: PW, height: PH },
                                          hasTouch: true, isMobile: true, deviceScaleFactor: 2 });
  const pp = await pctx.newPage();
  watch(pp);
  await pp.goto(URL_, { waitUntil: "load" });
  await pp.waitForSelector("#play:not([disabled])", { timeout: 180000 });
  await pp.tap("#play");
  await pp.waitForTimeout(1500);
  const pcv = await pp.evaluate(() => { const c = document.getElementById("canvas"); return [c.width, c.height]; });
  check(pcv[0] === PW && pcv[1] === PH, `канвас под вертикальную вкладку: ${pcv[0]}×${pcv[1]}`);
  const ptitle = await pp.screenshot({ path: `${OUT}/web_10_portrait_title.png` });
  const pcdp = await pctx.newCDPSession(pp);
  const [psx, psy] = WP(960, 596);                 // «НАЧАТЬ» в кадре «лёжа»
  await pcdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: psx, y: psy }] });
  await pp.waitForTimeout(40);
  await pcdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  await pp.waitForTimeout(2500);
  const pgame = await pp.screenshot({ path: `${OUT}/web_11_portrait_game.png` });
  const dStart = await shotDiff(pp, ptitle, pgame);
  check(dStart > 0.08, `вертикальный телефон: кадр «лёжа», тап по повёрнутой «НАЧАТЬ» начал партию (кадр сменился на ${(dStart * 100).toFixed(1)} %)`);
  await pctx.close();

  // ---- запуск 5 (р.26): внутри Telegram (Mini App) ----
  // Telegram передаёт параметры запуска после «#»; SDK telegram.org подменён
  // заглушкой, которая записывает вызовы и, как настоящий Telegram, на весь
  // экран выставляет отступ под свои кнопки (--tg-content-safe-area-inset-top).
  const TG_INSET = 40;
  const TG_MOCK = `(function () {
    var calls = [], handlers = {};
    function fire(e) { (handlers[e] || []).forEach(function (f) { f(); }); }
    var wa = {
      _calls: calls, isFullscreen: false, isOrientationLocked: false,
      isVersionAtLeast: function (v) {
        var a = String(v).split("."), b = [8, 0];
        for (var i = 0; i < 2; i++) { var x = +(a[i] || 0); if (x !== b[i]) return x < b[i]; }
        return true;
      },
      ready: function () { calls.push("ready"); },
      expand: function () { calls.push("expand"); },
      setHeaderColor: function (c) { calls.push("header:" + c); },
      setBackgroundColor: function (c) { calls.push("background:" + c); },
      setBottomBarColor: function (c) { calls.push("bottombar:" + c); },
      disableVerticalSwipes: function () { calls.push("disableVerticalSwipes"); },
      requestFullscreen: function () {
        calls.push("requestFullscreen"); wa.isFullscreen = true;
        document.documentElement.style.setProperty("--tg-content-safe-area-inset-top", "${TG_INSET}px");
        fire("fullscreenChanged"); fire("contentSafeAreaChanged");
      },
      lockOrientation: function () { calls.push("lockOrientation"); wa.isOrientationLocked = true; },
      onEvent: function (e, f) { (handlers[e] = handlers[e] || []).push(f); }
    };
    window.Telegram = { WebApp: wa };
  })();`;
  const gctx = await browser.newContext({ viewport: { width: TW, height: TH },
                                          hasTouch: true, isMobile: true, deviceScaleFactor: 2 });
  await gctx.route(/telegram\.org\/js\/telegram-web-app\.js/, (r) =>
    r.fulfill({ status: 200, contentType: "application/javascript", body: TG_MOCK }));
  const gp = await gctx.newPage();
  watch(gp);
  await gp.goto(URL_ + "#tgWebAppData=query_id%3Dsmoke&tgWebAppVersion=8.0&tgWebAppPlatform=android",
                { waitUntil: "load" });
  await gp.waitForSelector("#play:not([disabled])", { timeout: 180000 });
  await gp.tap("#play");
  await gp.waitForTimeout(1500);
  const tgCalls = await gp.evaluate(() => (window.Telegram && window.Telegram.WebApp._calls) || []);
  const need = ["ready", "expand", "disableVerticalSwipes", "requestFullscreen", "lockOrientation"];
  const lost = need.filter((c) => tgCalls.indexOf(c) < 0);
  check(lost.length === 0, `Telegram: весь экран, свайп-закрытие отключено, горизонталь зафиксирована` +
        (lost.length ? ` — НЕ вызвано: ${lost.join(", ")}` : ` (${tgCalls.join(", ")})`));
  const gcv = await gp.evaluate(() => { const c = document.getElementById("canvas");
    return [c.width, c.height, Math.round(c.getBoundingClientRect().top)]; });
  check(gcv[1] === TH - TG_INSET && gcv[2] === TG_INSET,
        `Telegram: канвас отступил от его кнопок — ${gcv[0]}×${gcv[1]}, сверху ${gcv[2]} px`);
  await gp.screenshot({ path: `${OUT}/web_12_telegram.png` });
  await gctx.close();
  await browser.close();

  check(errors.length === 0, `ошибок в консоли/странице: ${errors.length}` + (errors.length ? " — " + errors.slice(0, 3).join(" | ") : ""));
  check(dialogs.length === 0, `алертов: ${dialogs.length}` + (dialogs.length ? " — " + dialogs.join(" | ") : ""));
  console.log(fails.length ? `WEB SMOKE FAIL (${fails.length})` : "WEB SMOKE PASS");
  process.exit(fails.length ? 1 : 0);
})().catch((e) => { console.error(e); console.log("WEB SMOKE FAIL"); process.exit(1); });
