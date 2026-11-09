# FHD_Navigator 0.2.1 — SCRIPT_NODLL_TEST

[Установочный ZIP](install/FHD_Navigator_0.2.1_SCRIPT_NODLL_TEST.zip) — оригинальный архив из 5 игровых файлов, SHA-256 `9647e6adf92c1c0eb1366e0ba4311fd851c667f76eb323e4b75783f4fe1ed34f`.

## Содержимое

- `SOURCE/CFG/CacheData.dat.json` — редактируемый CacheData
- `SOURCE/CFG/Main.dat.json` — редактируемый Main
- `SOURCE/CFG/Rus/Lang.dat.json` — редактируемый русский Lang
- `SOURCE/Data/Image/RouteFrame.png` — редактируемое изображение рамки
- `SOURCE/ModuleInfo.txt` — редактируемый UTF-8 текст настроек мода (оригинал в ZIP — Windows-1251; сборщик сохраняет эту кодировку)
- `tools/build_source.py` — извлечение и точечная пересборка исходников
- `tools/dat_codec.py` — кодек BlockPar/CacheData из опубликованного DevKit
- `ORIGINAL_FILE_SHA256.json`, `SOURCE_HASHES.json` — манифесты проверок

Для пересборки без изменений: `python tools/build_source.py --verify`. Для преобразования изменённого PNG нужен Python-пакет `srhd_modkit` (XenoModKit). При отсутствии изменений сборщик сохраняет ZIP побайтно. DAT исходники проверяются декодированием и обратным кодированием.

Версия **TEST** и **без DLL**. Не является финальным релизом. Отдельное тестирование работы в игре, совместимости с другими модами и обеими версиями EXE не проводилось. Старые версии не изменены.
