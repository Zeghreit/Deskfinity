# Deskfinity

A lightweight desktop icon organizer for Windows. Draw a named box on your
wallpaper and drop a group of shortcuts into it — they arrange themselves into a
proportional grid, and the originals are physically moved off the desktop.

One Python file plus PyQt6. No installer, no background service, no shell
replacement.

*Русская версия — [ниже](#deskfinity-русский).*

---

## Install

**Ready-made exe:** download `Deskfinity.exe` from the
[Releases](https://github.com/Zeghreit/Deskfinity/releases) page — no Python
needed. Every push also builds one, under
[Actions](https://github.com/Zeghreit/Deskfinity/actions) → the run →
*Artifacts*. To keep the data next to the exe, create a `DeskfinityData`
folder beside it (see *Portable mode* below).

**From source:**

1. Put `deskfinity.py` and `Deskfinity.bat` in the same folder.
2. Run `Deskfinity.bat`. It installs PyQt6 if missing and starts the app with
   `pythonw` (no console window).

Manually:

```
pip install PyQt6
pythonw deskfinity.py
```

## Usage

| Action | How |
|---|---|
| Create a box | Click the tray icon, or **Ctrl+Alt+F** (change it: tray → **Hotkey…**), then drag out an area |
| Add shortcuts | Drag files/folders from Explorer into the box |
| Rename a box | Double-click the header |
| Open an item | Double-click the icon |
| Reorder icons | Drag inside the box (an insert marker appears) |
| Select several | Ctrl+click / Shift+click, like in Explorer |
| Move to another box | Drag onto it, or right-click → **Move to box** |
| Take out | Drag onto the desktop or into an Explorer window |
| Move / resize | Drag the header / the edges (7 px hit zone). Boxes snap to screen edges and to each other; hold **Alt** to place freely |
| Scroll | Mouse wheel, when there are more icons than fit |
| Settings | Right-click inside the box |
| Auto-sort | Right-click → **Auto-sort rules…** |

## Moving vs. referencing

By default a box **takes ownership** of desktop items you drop into it: the file
is moved into `%APPDATA%\Deskfinity\storage\<box-id>\`, so it disappears from the
desktop on its own. No need to hide desktop icons.

Only items lying directly on the Desktop (yours or the Public one) are moved.
Anything dropped from another folder or drive stays where it is and the box just
links to it — dragging in `D:\Projects` will not relocate your project.

- **Move files into box** — toggle per box. Turn it off and the box only keeps
  references, leaving originals where they are.
- **Move originals into box** — retrofits entries that were added before the
  feature existed.
- **Send to desktop** — the reverse: moves a stored file back onto the desktop
  and drops it from the box. Dragging it onto the desktop does the same.
- Moving items to another box takes stored files along into that box's
  storage; links stay links.
- **Open box folder** — opens the storage folder in Explorer.

Shortcuts living in `C:\Users\Public\Desktop` need administrator rights to move.
Deskfinity detects the failure, lists the affected items and offers a single
elevated retry for the whole batch. Note that those shortcuts are shared by every
account on the machine.

Deleting a box that holds files asks what to do with them — send them to the
desktop, or leave them in storage.

## Auto-sort rules

Give a box name patterns and new things that land on your Desktop go into it
by themselves — downloads, screenshots, saved attachments.

- Patterns are separated by `;`: `*.pdf; *.docx; Screenshot*`. `*` and `?` are
  wildcards, case doesn't matter. A trailing `/` matches folders instead of
  files: `*/` is every folder, `Photos*/` only matching ones.
- One-click presets: Documents, Images, Video, Music, Archives, Installers,
  Shortcuts, Folders.
- A new item is sorted once it has been quiet for a few seconds, so a running
  download, a copy in progress or a rename you are typing is not snatched.
  Temporary, hidden and system files (`*.crdownload`, `~$…`, `desktop.ini`) are
  never touched. A file that is in use is retried a few times.
- Only new items are sorted automatically. **Tray → Sort desktop by rules**
  (or answering "yes" after editing rules) applies them to what is already
  there, including the Public desktop.
- If several boxes match, the first one wins. **Send to desktop** keeps an item
  on the desktop — it is not sorted straight back.
- A box with rules shows a small dot in its header; hover it to see them.

## Per-box settings (right-click)

- Background colour
- Opacity — a live 0–255 slider in the menu
- Label colour
- Icon size — 32 / 40 / 48 / 64 / 80 / 96 px
- Corner radius — 0 / 6 / 10 / 16 / 24
- Sort by name or by type
- Collapse to header — a collapsed box rolls open while you hover it (or drag
  files over it) and rolls back up when the mouse leaves
- Lock — blocks moving and resizing
- Remove broken links
- Auto-sort rules

## How it works

- Icons come from the Windows system cache at **jumbo (256×256)** size via
  `SHGetImageList` + `IImageList::GetIcon`, so they stay sharp at 96 px. The
  `HICON` is converted to a `QImage` through `GetIconInfo`/`GetDIBits`, with the
  alpha channel rebuilt from the mask when the icon has none. Transparent
  padding is cropped automatically.
- Icons reflow with **proportional** spacing: changing the width changes the
  column count, and the leftover space is split evenly between the gaps.
- Boxes stay **below every other window** by intercepting
  `WM_WINDOWPOSCHANGING` and forcing `HWND_BOTTOM`. They never appear in the
  taskbar (`Qt.Tool`).
- Broken links are drawn dimmed.
- Unplug a monitor and its boxes are parked on the main screen; plug it back
  in and they return to their own spot (that spot is what stays saved).
- Only one copy runs per user: launching it again just brings the boxes back
  and points at the tray icon.

## Data

Config: `%APPDATA%\Deskfinity\boxes.json` — plain JSON, safe to edit by hand.

**Portable mode:** create a `DeskfinityData` folder next to `deskfinity.py` or
`Deskfinity.exe` (one level up also works, for an exe built into `dist\`) and
everything below — config, storage, log — lives there instead of `%APPDATA%`.
The `DESKFINITY_DATA` environment variable points it anywhere else.
Files owned by boxes live in `%APPDATA%\Deskfinity\storage\`. The tray menu has
an "open settings folder" entry.

Safety net:

- On every start the config is copied to `boxes.json.bak1` (up to `bak3`).
- If `boxes.json` is damaged, it is kept as `boxes.json.broken-<date>` and the
  layout is restored from the newest readable backup. A box that fails to load
  is kept in the file untouched instead of being dropped.
- **Tray → Recover files from storage** turns any storage folder no box owns
  (e.g. after "leave in storage" on delete) back into a box.

Log: `%APPDATA%\Deskfinity\deskfinity.log` — errors, plus every file the app
moves (from where to where), so nothing gets lost without a trace.

The interface speaks English or Russian, following the Windows language;
tray → **Язык / Language** switches it.

Autostart is toggled from the tray and writes to
`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.

## Limitations

- Windows only — icon extraction and z-order rely on WinAPI.
- **"This PC" and "Recycle Bin" cannot be moved.** They are virtual shell
  namespace objects with no file on disk. Support for holding them as items
  (addressed by parsing name, e.g. `::{645FF040-5081-101B-9F08-00AA002F954E}`)
  is in progress; their native desktop icons are switched off separately via
  Personalisation → Themes → Desktop icon settings.
- No quick-hide of all boxes by double-clicking empty desktop.

## Tests

```
pip install PyQt6
python -m unittest discover -s tests
```

They run headless (`QT_QPA_PLATFORM=offscreen`) on any OS and cover file
moving, config rescue, resizing, single instance, HiDPI icons, background
status checks, screen changes and auto-sort rules. The WinAPI parts (icon extraction, z-order,
UAC retry) still need a manual check on Windows.

## License

MIT — see [LICENSE](LICENSE).

---

<a name="deskfinity-русский"></a>

# Deskfinity (русский)

Лёгкий органайзер иконок рабочего стола для Windows. Рисуешь на обоях именованный
бокс и складываешь в него группу ярлыков — они раскладываются по сетке, а
оригиналы физически уезжают с рабочего стола.

Один файл на Python + PyQt6. Без установщика, без фоновых служб и без подмены
оболочки.

## Установка

**Готовый exe:** скачай `Deskfinity.exe` со страницы
[Releases](https://github.com/Zeghreit/Deskfinity/releases) — Python не нужен.
Каждый push тоже собирает exe: [Actions](https://github.com/Zeghreit/Deskfinity/actions)
→ нужный запуск → *Artifacts*. Чтобы данные лежали рядом с exe, создай рядом
папку `DeskfinityData` (см. *Портативный режим* ниже).

**Из исходников:**

1. Положи `deskfinity.py` и `Deskfinity.bat` в одну папку.
2. Запусти `Deskfinity.bat` — он поставит PyQt6, если его нет, и стартанёт
   приложение через `pythonw` (без окна консоли).

Вручную:

```
pip install PyQt6
pythonw deskfinity.py
```

## Как пользоваться

| Действие | Как |
|---|---|
| Создать бокс | Клик по иконке в трее, или **Ctrl+Alt+F** (сменить: трей → **Сочетание клавиш…**) → обвести область |
| Добавить ярлыки | Перетащить файлы/папки из проводника в бокс |
| Переименовать бокс | Двойной клик по заголовку |
| Открыть элемент | Двойной клик по иконке |
| Переставить иконки | Перетащить внутри бокса (появляется маркер вставки) |
| Выделить несколько | Ctrl+клик / Shift+клик, как в проводнике |
| Перенести в другой бокс | Перетащить на него или ПКМ → **Переместить в бокс** |
| Вынуть | Перетащить на рабочий стол или в окно проводника |
| Двигать / менять размер | Тянуть за заголовок / за края (7 px зона). Боксы прилипают к краям экрана и друг к другу; с **Alt** — свободно |
| Прокрутка | Колесо мыши, если иконок больше, чем влезает |
| Настройки | ПКМ внутри бокса |
| Автосортировка | ПКМ → **Правила автосортировки…** |

## Перенос против ссылок

По умолчанию бокс **забирает себе** элементы рабочего стола: то, что ты в него
бросаешь, переезжает в `%APPDATA%\Deskfinity\storage\<id бокса>\`, поэтому со
стола оно исчезает само. Скрывать значки не нужно.

Переносится только то, что лежит прямо на рабочем столе (твоём или общем).
Всё, что брошено из других папок и дисков, остаётся на месте — бокс просто
хранит ссылку. Перетащив `D:\Projects`, ты не переселишь свой проект.

- **Переносить файлы в бокс** — переключатель для каждого бокса отдельно. Сними
  галочку, и бокс будет хранить только ссылки, не трогая оригиналы.
- **Перенести оригиналы в бокс** — дотягивает те элементы, которые добавлялись
  до появления этой логики.
- **Вынести на рабочий стол** — обратная операция: файл возвращается на стол и
  убирается из бокса. Перетащить его на стол — то же самое.
- При переносе в другой бокс файлы из хранилища переезжают в хранилище нового
  бокса, ссылки остаются ссылками.
- **Открыть папку бокса** — открывает хранилище в проводнике.

Ярлыки из `C:\Users\Public\Desktop` требуют прав администратора. Deskfinity
ловит отказ, показывает список и предлагает повторить с повышением прав одним
запросом UAC на всю пачку. Учти, что эти ярлыки общие для всех учёток машины.

При удалении бокса с файлами внутри спрашивается, что с ними делать — вынести на
стол или оставить в хранилище.

## Правила автосортировки

Задай боксу шаблоны имён, и новое на рабочем столе само будет в него
попадать — загрузки, скриншоты, сохранённые вложения.

- Шаблоны через `;`: `*.pdf; *.docx; Скриншот*`. `*` и `?` — подстановочные
  знаки, регистр не важен. `/` в конце означает папки вместо файлов: `*/` — все
  папки, `Фото*/` — только подходящие.
- Готовые наборы в один клик: Документы, Картинки, Видео, Музыка, Архивы,
  Установщики, Ярлыки, Папки.
- Новый элемент сортируется, когда он несколько секунд не меняется, — идущая
  загрузка, незаконченное копирование или переименование не перехватываются.
  Временные, скрытые и системные файлы (`*.crdownload`, `~$…`, `desktop.ini`)
  не трогаются никогда. Занятый файл пробуется ещё несколько раз.
- Автоматически сортируется только новое. **Трей → Разложить рабочий стол по
  правилам** (или «да» после правки правил) применяет их к тому, что уже лежит,
  включая общий рабочий стол.
- Если подходят несколько боксов, побеждает первый. **Вынести на рабочий стол**
  оставляет элемент на столе — обратно он не уедет.
- У бокса с правилами в заголовке маленькая точка; наведи на неё — увидишь
  правила.

## Настройки бокса (ПКМ)

- Цвет подложки
- Прозрачность — живой слайдер 0–255 прямо в меню
- Цвет текста
- Размер иконок — 32 / 40 / 48 / 64 / 80 / 96 px
- Скругление углов — 0 / 6 / 10 / 16 / 24
- Сортировка по имени или по типу
- Свернуть в заголовок — свёрнутый бокс раскрывается, пока над ним мышь (или
  над ним тащат файлы), и сворачивается обратно, когда она уходит
- Зафиксировать — блокирует перемещение и ресайз
- Убрать битые ссылки
- Правила автосортировки

## Как это работает

- Иконки берутся из системного кэша Windows в размере **jumbo (256×256)** через
  `SHGetImageList` + `IImageList::GetIcon`, поэтому на 96 px не мылятся. `HICON`
  конвертируется в `QImage` через `GetIconInfo`/`GetDIBits`, альфа при
  отсутствии восстанавливается из маски. Прозрачные поля обрезаются
  автоматически.
- Раскладка **пропорциональная**: при изменении ширины меняется число колонок, а
  остаток делится поровну между промежутками.
- Боксы держатся **под всеми окнами** через перехват `WM_WINDOWPOSCHANGING` с
  принудительным `HWND_BOTTOM`. В таскбаре не светятся (`Qt.Tool`).
- Битые ссылки рисуются полупрозрачными.
- Отключил монитор — его боксы переезжают на основной экран; подключил обратно —
  возвращаются на своё место (в конфиге хранится именно оно).
- Запускается только одна копия на пользователя: повторный запуск просто
  показывает боксы и подсказывает, что программа уже в трее.

## Данные

Конфиг: `%APPDATA%\Deskfinity\boxes.json` — обычный JSON, можно править руками.

**Портативный режим:** создай папку `DeskfinityData` рядом с `deskfinity.py` или
`Deskfinity.exe` (можно на уровень выше — для exe, собранного в `dist\`), и всё
описанное ниже — конфиг, хранилище, журнал — будет лежать там, а не в
`%APPDATA%`. Переменная окружения `DESKFINITY_DATA` задаёт любое другое место.
Файлы боксов лежат в `%APPDATA%\Deskfinity\storage\`. В трее есть пункт
«Открыть папку настроек».

Страховка:

- При каждом запуске конфиг копируется в `boxes.json.bak1` (до `bak3`).
- Если `boxes.json` повреждён, он сохраняется как `boxes.json.broken-<дата>`, а
  раскладка восстанавливается из свежей читаемой копии. Бокс, который не
  загрузился, остаётся в файле нетронутым, а не теряется.
- **Трей → Восстановить файлы из хранилища** превращает папки хранилища, которые
  не принадлежат ни одному боксу (например, после «оставить в хранилище» при
  удалении), обратно в бокс.

Журнал: `%APPDATA%\Deskfinity\deskfinity.log` — ошибки и каждый перенос файла
(откуда и куда), чтобы ничего не терялось бесследно.

Интерфейс на русском или английском — по языку Windows; переключается в
трее: **Язык / Language**.

Автозапуск включается из трея и пишет ключ в
`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.

## Ограничения

- Только Windows — извлечение иконок и z-order завязаны на WinAPI.
- **«Этот компьютер» и «Корзина» перенести нельзя.** Это виртуальные объекты
  пространства имён оболочки, файла на диске у них нет. Поддержка их хранения
  как элементов бокса (по parsing name, например
  `::{645FF040-5081-101B-9F08-00AA002F954E}`) в работе; родные значки при этом
  отключаются отдельно: Персонализация → Темы → Параметры значков рабочего стола.
- Нет быстрого скрытия всех боксов по двойному клику на пустом месте стола.

## Тесты

`python -m unittest discover -s tests` — работают без экрана на любой ОС. Части
на WinAPI (иконки, z-order, повтор через UAC) по-прежнему проверяются вручную
на Windows.

## Лицензия

MIT — см. [LICENSE](LICENSE).
