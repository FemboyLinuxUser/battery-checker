# battery-checker

Windows-утилита в системном трее для мониторинга заряда беспроводных устройств:

- клавиатуры AULA F108 Pro через USB HID-донгл;
- Bluetooth-устройств через Windows SetupAPI.

Поверх экрана показывается компактный оверлей: ряд маленьких батареек с иконкой типа устройства. Зелёная заливка — нормальный заряд, красная — заряд ниже порога, серая — нет данных или устройство отключено. В трее отображается худший заряд, а в меню — состояние каждого устройства.

## Возможности

- настраиваемые пороги низкого и полного заряда;
- повторное звуковое уведомление при дальнейшем разряде ниже порога;
- звуки из WAV-файла или сгенерированного тона;
- настройка состава устройств, положения и прозрачности оверлея;
- список Bluetooth-устройств без PowerShell, с пометкой устройств, у которых Windows видит заряд;
- уведомления в системном трее;
- история разряда в SQLite с графиком за сутки/неделю/месяц;
- автозапуск с Windows;
- логирование в файл.

## Требования

- Windows 10/11;
- Python 3.10+ для запуска из исходников;
- зависимости из `requirements.txt`.

## Запуск из исходников

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Сборка exe

```powershell
pip install -r requirements-dev.txt
pyinstaller battery_mon.spec
```

Готовый файл будет в `dist\battery_mon.exe`.

## Конфиг, логи и история

При запуске создаётся каталог:

```text
%APPDATA%\battery-checker\
```

В нём находятся:

- `config.yaml` — пользовательская конфигурация;
- `battery-checker.log` — rotating-лог приложения;
- `history.db` — SQLite-база истории заряда.

Если рядом с exe или `main.py` найден старый `config.yaml`, при первом запуске он копируется в `%APPDATA%\battery-checker\config.yaml`.

## Тесты

```powershell
pip install -r requirements-dev.txt
pytest
```

## Структура

- `main.py` — точка входа;
- `app.py` — `AppController` и runtime-состояние приложения;
- `overlay.py` — оверлей батареек;
- `settings.py` — настройки, редакторы звуков и график истории;
- `poller.py` — фоновый поток опроса;
- `devices.py` — сборка и опрос устройств;
- `bt_battery_ctypes.py` — Bluetooth/SetupAPI без PowerShell;
- `aula_battery.py` — USB HID-протокол AULA;
- `history.py` — SQLite-история;
- `autostart.py` — автозапуск через реестр;
- `tray.py` — иконка трея;
- `beep_sound.py` — воспроизведение звуков.

## TODO

- тёмная/светлая тема оверлея и выбор цветов;
- экспорт состояния по HTTP/JSON для внешних виджетов (Rainmeter и т.п.).
