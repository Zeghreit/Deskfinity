# Deskfinity

A lightweight desktop icon organizer for Windows. Draw a named box on your
wallpaper and drop a group of shortcuts into it — they arrange themselves into a
proportional grid, and the originals are physically moved off the desktop.

One Python file plus PyQt6. No installer, no background service, no shell
replacement.

*Русская версия — [ниже](#deskfinity-русский).*

---

## Install

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
| Create a box | Click the tray icon, or **Ctrl+Alt+F**, then drag out an area |
| Add shortcuts | Drag files/folders from Explorer into the box |
| Rename a box | Double-click the header |
| Open an item | Double-click the icon |
| Reorder icons | Drag inside the box (an insert marker appears) |
| Move / resize | Drag the header / the edges (7 px hit zone) |
| Scroll | Mouse wheel, when there are more icons than fit |
| Settings | Right-click inside the box |

## Moving vs. referencing

By default a box **takes ownership** of what you drop into it: the file is moved
into `%APPDATA%\Deskfinity\storage\<box-id>\`, so it disappears from the desktop
on its own. No need to hide desktop icons.

- **Move files into box** — toggle per box. Turn it off and the box only keeps
  references, leaving originals where they are.
- **Move originals into box** — retrofits entries that were added before the
  feature existed.
- **Send to desktop** — the reverse: moves a stored file back onto the desktop
  and drops it from the box.
- **Open box folder** — opens the storage folder in Explorer.

Shortcuts living in `C:\Users\Public\Desktop` need administrator rights to move.
Deskfinity detects the failure, lists the affected items and offers a single
elevated retry for the whole batch. Note that those shortcuts are shared by every
account on the machine.

Deleting a box that holds files asks what to do with them — send them to the
desktop, or leave them in storage.

## Per-box settings (right-click)

- Background colour
- Opacity — a live 0–255 slider in the menu
- Label colour
- Icon size — 32 / 40 / 48 / 64 / 80 / 96 px
- Corner radius — 0 / 6 / 10 / 16 / 24
- Sort by name or by type
- Collapse to header
- Lock — blocks moving and resizing
- Remove broken links

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

## Data

Config: `%APPDATA%\Deskfinity\boxes.json` — plain JSON, safe to edit by hand.
Files owned by boxes live in `%APPDATA%\Deskfinity\storage\`. The tray menu has
an "open settings folder" entry.

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
| Создать бокс | Клик по иконке в трее, или **Ctrl+Alt+F** → обвести область |
| Добавить ярлыки | Перетащить файлы/папки из проводника в бокс |
| Переименовать бокс | Двойной клик по заголовку |
| Открыть элемент | Двойной клик по иконке |
| Переставить иконки | Перетащить внутри бокса (появляется маркер вставки) |
| Двигать / менять размер | Тянуть за заголовок / за края (7 px зона) |
| Прокрутка | Колесо мыши, если иконок больше, чем влезает |
| Настройки | ПКМ внутри бокса |

## Перенос против ссылок

По умолчанию бокс **забирает файл себе**: то, что ты в него бросаешь,
переезжает в `%APPDATA%\Deskfinity\storage\<id бокса>\`, поэтому с рабочего
стола оно исчезает само. Скрывать значки не нужно.

- **Переносить файлы в бокс** — переключатель для каждого бокса отдельно. Сними
  галочку, и бокс будет хранить только ссылки, не трогая оригиналы.
- **Перенести оригиналы в бокс** — дотягивает те элементы, которые добавлялись
  до появления этой логики.
- **Вынести на рабочий стол** — обратная операция: файл возвращается на стол и
  убирается из бокса.
- **Открыть папку бокса** — открывает хранилище в проводнике.

Ярлыки из `C:\Users\Public\Desktop` требуют прав администратора. Deskfinity
ловит отказ, показывает список и предлагает повторить с повышением прав одним
запросом UAC на всю пачку. Учти, что эти ярлыки общие для всех учёток машины.

При удалении бокса с файлами внутри спрашивается, что с ними делать — вынести на
стол или оставить в хранилище.

## Настройки бокса (ПКМ)

- Цвет подложки
- Прозрачность — живой слайдер 0–255 прямо в меню
- Цвет текста
- Размер иконок — 32 / 40 / 48 / 64 / 80 / 96 px
- Скругление углов — 0 / 6 / 10 / 16 / 24
- Сортировка по имени или по типу
- Свернуть в заголовок
- Зафиксировать — блокирует перемещение и ресайз
- Убрать битые ссылки

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

## Данные

Конфиг: `%APPDATA%\Deskfinity\boxes.json` — обычный JSON, можно править руками.
Файлы боксов лежат в `%APPDATA%\Deskfinity\storage\`. В трее есть пункт
«Открыть папку настроек».

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

## Лицензия

MIT — см. [LICENSE](LICENSE).
