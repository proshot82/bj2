#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Веб-версия (р.24): сборка игры для браузера → dist/web/.

Рантайм — love.js (Davidobot/love.js, MIT): LÖVE 11.5, собранный в
WebAssembly, — тот же движок, что в релизе для Windows. Пакет love.js в npm
застрял на 11.4 (2022), а сборка 11.5 живёт только в репозитории, поэтому
файлы рантайма берутся оттуда с закреплённого коммита и сверяются с зашитыми
SHA-256 — ни Node, ни чужой код на сборке не нужны. Кэш — work/web_cache/.
Вариант compatibility (без потоков): ему не нужны заголовки COOP/COEP, и он
работает на любом статическом хостинге, включая GitHub Pages и itch.io.

Одна правка рантайма: love.js кладёт сейвы в IndexedDB только по
beforeunload, и при закрытии вкладки асинхронная запись не успевает —
последний прогресс теряется. Сборка выставляет наружу объект FS
(Module.FS), а оболочка web/index.html синхронизирует сейвы сама: раз в
3 с, при сворачивании вкладки и на pagehide.

Шаги:
  1. Поставочное дерево — то же, что в .love релиза (main.lua conf.lua src
     assets design, BUILDLOG «Фаза 6»), копируется во временный каталог.
  2. Фоны (rooms/, zooms/, ui/bg_title.png, ui/paper_reader.png) — 19
     полноэкранных картинок без прозрачности, 55 МБ из 78 — перекодируются в
     JPEG q90 без прореживания цвета (4:4:4) под ТЕМИ ЖЕ именами .png: LÖVE
     выбирает декодер по содержимому файла, а не по расширению, поэтому ни
     scene.json, ни код не меняются. Загрузка 78 → ~33 МБ, PSNR 39–44 дБ
     (на глаз не отличить, сравнение кропами ×2 — р.24). Полупрозрачные
     пиксели (их ~1000 на zoom_drawer_keypad) сперва кладутся на чёрный —
     ровно так их и показывает игра: фон зума рисуется поверх чёрной очистки.
     Ключ --lossless оставляет PNG как есть. Релиз для Windows не трогается.
  3. game.love — детерминированный zip: фиксированные даты, сортировка;
     картинки, звук и шрифты кладутся без сжатия (они уже сжаты, а inflate в
     WebAssembly — лишние секунды загрузки).
  4. game.js (загрузчик love.js, метаданные пакета; uuid пакета выводится из
     SHA-256 данных — кэш браузера живёт ровно до смены содержимого),
     index.html (оболочка web/index.html), love.js/love.wasm, licenses.txt.
  5. Сводка: размеры и SHA-256. --zip кладёт рядом dist/BrassJanissary2-web.zip
     (для itch.io: index.html в корне архива). --serve [порт] поднимает
     локальный сервер на 127.0.0.1 для проверки в браузере.

Запуск из корня репозитория:  python3 tools/build_web.py [--lossless] [--zip] [--serve [PORT]]
"""
import argparse, datetime, hashlib, http.server, io, json, os, shutil
import subprocess, sys, tempfile, urllib.request, uuid, zipfile

if not os.path.isdir("design") or not os.path.isfile("main.lua"):
    sys.exit("запускать из корня репозитория")

# Davidobot/love.js, коммит «11.5 working with emscripten 2.0.0» (2024-05-13)
LOVEJS_COMMIT = "c4f04e185033a7c9fbefa9be3bec88c41a90421b"
LOVEJS_RAW = f"https://raw.githubusercontent.com/Davidobot/love.js/{LOVEJS_COMMIT}/"
LOVEJS_FILES = {   # путь в репозитории love.js → (имя у нас, SHA-256)
    "src/compat/love.js": ("love.js",
        "86a993add89e4b62af875995ad954f39a23725f3f48553a1618b520738b228a0"),
    "src/compat/love.wasm": ("love.wasm",
        "8e955d3ca1db20c2c3509313c0093cf81826fc391f509194f85562ac57c601fa"),
    "src/game.js": ("game.js.tpl",
        "f679c9694c01fab535951fa5945f816745c0592fe66b0032de3e6f1656853d8c"),
    "LICENSE": ("LICENSE",
        "a5c6a1286581e6a104f81647835791b7ec4148dcf1951633d23fcb3198f7c7fb"),
}
# точка, где рантайм монтирует IDBFS: сразу за ней FS выставляется наружу
FS_ANCHOR = 'FS.mount(IDBFS,{},"/home/web_user/love");'
CACHE = "work/web_cache"
OUT = "dist/web"
ZIP_OUT = "dist/BrassJanissary2-web.zip"
TITLE = "Латунный янычар 2.0"
TREE = ["main.lua", "conf.lua", "src", "assets", "design"]   # как .love релиза
BACKGROUNDS = ["assets/gfx/rooms", "assets/gfx/zooms",
               "assets/gfx/ui/bg_title.png", "assets/gfx/ui/paper_reader.png"]
JPEG_Q = 90
STORED = (".png", ".jpg", ".ogg", ".ttf")   # уже сжаты — без deflate
ZIP_DATE = (2019, 1, 1, 0, 0, 0)            # детерминизм: одна дата на всё
MB = 1024 * 1024


def fetch_lovejs():
    """Файлы рантайма love.js с закреплённого коммита, сверка SHA-256;
    возвращает {имя: bytes}. Скачанное кэшируется в work/web_cache/."""
    cache = os.path.join(CACHE, LOVEJS_COMMIT[:12])
    os.makedirs(cache, exist_ok=True)
    out = {}
    for path, (name, sha) in LOVEJS_FILES.items():
        p = os.path.join(cache, name)
        if not os.path.exists(p):
            print(f"[web] качаю {LOVEJS_RAW}{path}")
            with urllib.request.urlopen(LOVEJS_RAW + path, timeout=120) as r:
                open(p + ".part", "wb").write(r.read())
            os.replace(p + ".part", p)
        data = open(p, "rb").read()
        got = hashlib.sha256(data).hexdigest()
        if got != sha:
            os.remove(p)
            sys.exit(f"[web] SHA-256 {path} не совпал (получено {got}) — "
                     f"файл удалён из кэша, сборка остановлена")
        out[name] = data
    js = out["love.js"].decode("utf-8")
    if js.count(FS_ANCHOR) != 1:
        sys.exit("[web] в love.js не найдена точка монтирования IDBFS — "
                 "рантайм не тот, синхронизация сейвов не встанет")
    out["love.js"] = js.replace(FS_ANCHOR, FS_ANCHOR + "Module.FS=FS;").encode("utf-8")
    return out


def is_background(rel):
    rel = rel.replace(os.sep, "/")
    return any(rel == b or rel.startswith(b + "/") for b in BACKGROUNDS)


def to_jpeg(path):
    """PNG → JPEG q90 4:4:4 под тем же именем; возвращает (до, после) байт."""
    from PIL import Image
    before = os.path.getsize(path)
    im = Image.open(path)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        black = Image.new("RGBA", im.size, (0, 0, 0, 255))
        im = Image.alpha_composite(black, im)
    rgb = im.convert("RGB")
    buf = io.BytesIO()
    rgb.save(buf, "JPEG", quality=JPEG_Q, subsampling=0, optimize=True)
    open(path, "wb").write(buf.getvalue())
    return before, len(buf.getvalue())


def stage(tmp, lossless):
    for item in TREE:
        src = item
        dst = os.path.join(tmp, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    if lossless:
        print("[web] --lossless: фоны остаются PNG")
        return
    n = b0 = b1 = 0
    for root, _, files in os.walk(os.path.join(tmp, "assets")):
        for f in sorted(files):
            p = os.path.join(root, f)
            rel = os.path.relpath(p, tmp)
            if f.endswith(".png") and is_background(rel):
                a, b = to_jpeg(p)
                n += 1; b0 += a; b1 += b
    print(f"[web] фоны → JPEG q{JPEG_Q} 4:4:4: {n} файлов, "
          f"{b0 / MB:.1f} → {b1 / MB:.1f} МБ")


def make_love(tmp):
    files = []
    for item in TREE:
        p = os.path.join(tmp, item)
        if os.path.isdir(p):
            for root, _, fs in os.walk(p):
                for f in fs:
                    files.append(os.path.relpath(os.path.join(root, f), tmp))
        else:
            files.append(item)
    files.sort()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for rel in files:
            arc = rel.replace(os.sep, "/")
            zi = zipfile.ZipInfo(arc, date_time=ZIP_DATE)
            zi.external_attr = 0o644 << 16
            stored = arc.lower().endswith(STORED)
            zi.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
            z.writestr(zi, open(os.path.join(tmp, rel), "rb").read(),
                       compresslevel=None if stored else 9)
    return buf.getvalue(), len(files)


def font_notice(path):
    """Копирайт и лицензия, зашитые в сам шрифт (таблица name, id 0 и 13)."""
    import struct
    data = open(path, "rb").read()
    num = struct.unpack(">H", data[4:6])[0]
    for i in range(num):
        tag, _, off, _ = struct.unpack(">4sIII", data[12 + 16 * i:28 + 16 * i])
        if tag != b"name":
            continue
        _, count, so = struct.unpack(">HHH", data[off:off + 6])
        rec = {}
        for j in range(count):
            pid, _, lid, nid, ln, o = struct.unpack(
                ">HHHHHH", data[off + 6 + 12 * j:off + 18 + 12 * j])
            if pid == 3 and lid == 0x409 and nid in (0, 13):
                rec[nid] = data[off + so + o:off + so + o + ln].decode("utf-16-be")
        return (rec.get(0, "") + "\n\n" + rec.get(13, "")).replace("\r\n", "\n")
    return ""


LOVE_ZLIB = """\
Copyright (c) 2006-2023 LOVE Development Team

This software is provided 'as-is', without any express or implied
warranty.  In no event will the authors be held liable for any damages
arising from the use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it
freely, subject to the following restrictions:

1. The origin of this software must not be misrepresented; you must not
   claim that you wrote the original software. If you use this software
   in a product, an acknowledgment in the product documentation would be
   appreciated but is not required.
2. Altered source versions must be plainly marked as such, and must not be
   misrepresented as being the original software.
3. This notice may not be removed or altered from any source distribution.
"""


def licenses(lovejs_license):
    parts = [
        f"{TITLE} — веб-версия. Сторонние компоненты и их лицензии.\n",
        "=" * 72,
        "love.js (https://github.com/Davidobot/love.js, коммит "
        f"{LOVEJS_COMMIT[:12]}) — веб-порт LÖVE: love.js, love.wasm, загрузчик "
        "game.js. Лицензия MIT:\n",
        lovejs_license.decode("utf-8").strip(),
        "=" * 72,
        "LÖVE 11.5 (https://love2d.org), собранный в love.wasm. Лицензия zlib.\n"
        "Тексты лицензий зависимостей LÖVE (SDL2, Lua, FreeType, libvorbis и др.):\n"
        "https://github.com/love2d/love/blob/11.5/license.txt\n",
        LOVE_ZLIB.strip(),
    ]
    for f in ("PTSans-Regular.ttf", "PTSans-Bold.ttf", "Neucha.ttf"):
        parts += ["=" * 72, f"Шрифт {f}:\n", font_notice("assets/fonts/" + f).strip()]
    return ("\n\n".join(parts) + "\n").encode("utf-8")


def build_id():
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", *TREE],
                               capture_output=True, text=True).stdout.strip()
        return sha + ("+правки" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "без git"


def main():
    ap = argparse.ArgumentParser(description="веб-версия на love.js → dist/web/")
    ap.add_argument("--lossless", action="store_true", help="фоны оставить PNG")
    ap.add_argument("--zip", action="store_true", help=f"ещё и {ZIP_OUT} для itch.io")
    ap.add_argument("--serve", nargs="?", const=8000, type=int, metavar="PORT",
                    help="после сборки поднять сервер на 127.0.0.1:PORT")
    args = ap.parse_args()

    rt = fetch_lovejs()
    tmp = tempfile.mkdtemp(prefix="bj2_web_")
    try:
        stage(tmp, args.lossless)
        love, nfiles = make_love(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    digest = hashlib.sha256(love).hexdigest()
    # Куча WebAssembly обязана вместить весь пакет до старта (love.js копирует
    # его в память целиком) плюс рабочий запас; дальше она растёт сама.
    memory = max(64 * MB, -(-(len(love) * 5 // 4 + 96 * MB) // (16 * MB)) * 16 * MB)
    meta = {"package_uuid": str(uuid.UUID(digest[:32])),
            "remote_package_size": len(love),
            "files": [{"filename": "/game.love", "crunched": 0, "start": 0,
                       "end": len(love), "audio": False}]}
    game_js = rt["game.js.tpl"].decode("utf-8")
    for tag in ("{{{create_file_paths}}}", "{{{metadata}}}"):
        if game_js.count(tag) != 1:
            sys.exit(f"[web] шаблон game.js love.js изменился: {tag} не найден")
    game_js = game_js.replace("{{{create_file_paths}}}", "")
    game_js = game_js.replace("{{{metadata}}}", json.dumps(meta))

    tpl = open("web/index.html", encoding="utf-8").read()
    stamp = datetime.date.today().isoformat()
    subst = {"%%TITLE%%": TITLE, "%%MEMORY%%": str(memory),
             "%%DATA_MB%%": f"{len(love) / MB:.0f}",
             "%%BUILD%%": f"{build_id()} от {stamp}"}
    for k, v in subst.items():
        if k not in tpl:
            sys.exit(f"[web] в web/index.html нет метки {k}")
        tpl = tpl.replace(k, v)

    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    out_files = {"index.html": tpl.encode("utf-8"), "game.js": game_js.encode("utf-8"),
                 "game.data": love, "love.js": rt["love.js"],
                 "love.wasm": rt["love.wasm"], "licenses.txt": licenses(rt["LICENSE"])}
    for name, data in out_files.items():
        open(os.path.join(OUT, name), "wb").write(data)

    total = sum(len(d) for d in out_files.values())
    print(f"[web] game.love: {nfiles} файлов, {len(love) / MB:.1f} МБ, "
          f"куча {memory // MB} МБ")
    print(f"[web] {OUT}/: {len(out_files)} файлов, {total / MB:.1f} МБ")
    for name in sorted(out_files):
        print(f"  {hashlib.sha256(out_files[name]).hexdigest()}  {name}")
    if args.zip:
        with zipfile.ZipFile(ZIP_OUT, "w", zipfile.ZIP_DEFLATED) as z:
            for name in sorted(out_files):
                zi = zipfile.ZipInfo(name, date_time=ZIP_DATE)
                zi.external_attr = 0o644 << 16
                zi.compress_type = (zipfile.ZIP_STORED if name in ("game.data", "love.wasm")
                                    else zipfile.ZIP_DEFLATED)
                z.writestr(zi, out_files[name])
        zd = open(ZIP_OUT, "rb").read()
        print(f"[web] {ZIP_OUT}: {len(zd) / MB:.1f} МБ")
        print(f"  {hashlib.sha256(zd).hexdigest()}  {os.path.basename(ZIP_OUT)}")
    print("WEB BUILD OK")

    if args.serve:
        os.chdir(OUT)
        handler = http.server.SimpleHTTPRequestHandler
        handler.extensions_map[".wasm"] = "application/wasm"
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", args.serve), handler)
        print(f"[web] http://127.0.0.1:{args.serve}/ — Ctrl+C для выхода")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
