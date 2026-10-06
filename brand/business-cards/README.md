# Визитки Pseudex

Брендовые визитки. **Бумага 90×50, матовая ламинация** — основной носитель.
Пластик 85.6×54 с NFC собран и отложен в `print/*-plastic*`.

## Идея

Лицевая сторона показывает то, что видит модель: контакты стоят под акцентными
плашками. Оборотная — то, что видит инструмент: те же три строки раскрыты, плюс QR
и NFC. Перевернул карточку — понял продукт. Подробно: [`BRANDBOOK.md`](BRANDBOOK.md).

![Макет](preview/card-mockup.png)

## Что где

| файл | что это |
|---|---|
| [`BRANDBOOK.md`](BRANDBOOK.md) | **главный документ**: идея, материал, палитра, сетка, NFC, ТЗ типографии |
| [`PRINT-SHORTLIST.md`](PRINT-SHORTLIST.md) | где напечатать к 8-му: звонки, цены, сроки, ловушки |
| [`CHATGPT-PROMPT.md`](CHATGPT-PROMPT.md) | промты для превью, мокапов и арта + что ChatGPT делать нельзя |
| [`print/build.py`](print/build.py) | генератор макета; люди и их контакты — в списке `PEOPLE` |
| `print/card-front-<имя>-paper.pdf` · `card-back-<имя>-paper.pdf` | **печатные файлы**: 94 × 54 мм (90×50 + 2 мм вылета), шрифты внедрены |
| `print/*-paper-90x50.pdf` | тот же макет **ровно по резу** (90 × 50) — если цеху удобнее без вылетов |
| `print/*-plastic*.pdf` | отложенный пластик 85.6 × 54 (для производства с NFC) |
| `print/spot-uv-mask.pdf` | маска под выборочный лак: только плашки, прозрачный фон |
| `preview/*-guides.png` | макет с направляющими реза и safe-зоны |
| `preview/card-mockup.png` | обе стороны рядом, для показа |
| [`nfc/card-igor.html`](nfc/card-igor.html) · [`nfc/card-gosha.html`](nfc/card-gosha.html) | **страницы, которые открывает метка**: контакты в один тап + документы для безопасника |
| [`nfc/team.html`](nfc/team.html) | индекс команды `/i/` — форма для случая, когда визиток станет несколько |
| [`nfc/igor.vcf`](nfc/igor.vcf) | контакт для кнопки «Сохранить контакт» |
| `fonts/` | Inter + JetBrains Mono с лицензиями (обе SIL OFL) |

## Что делать по шагам

**Сегодня (пн, вечер).**
1. Подставить настоящие телефон и почту **обоих**: список `PEOPLE` в
   [`print/build.py`](print/build.py), затем `PYTHONPATH=/tmp/pylibs python3 print/build.py`.
   Сейчас там заглушки. Вторая визитка — запись в этом списке, не второй макет.
2. Решить, куда ведёт метка, и убедиться, что этот адрес существует. По умолчанию —
   `https://pseudex.ru/i/igor` и `/i/gosha`; страницы готовы в `nfc/card-igor.html` и
   [`nfc/card-gosha.html`](nfc/card-gosha.html),
   её надо положить на этот адрес (рядом — `<имя>.vcf` и индекс `nfc/team.html`). **Если к 8-му не успевает —
   поменять URL на существующий**, а не печатать QR в пустоту.
3. Отправить письмо в 2–3 цеха из [`PRINT-SHORTLIST.md`](PRINT-SHORTLIST.md) с
   приложенными PDF — чтобы утром быть первыми в очереди. ТЗ готово: §7 брендбука.

**Утром 6-го.** Три звонка по списку. Спросить срок, наличие и — обязательно —
чип **NTAG213/215**, а не MIFARE Classic.

**7-го.** Забрать. **До тиража проверить одну карту** телефоном (iPhone и Android)
и QR камерой.

**8-е.** Дедлайн.

## Как пересобрать макет

```bash
pip install --target=/tmp/pylibs segno            # QR
printf '<fontconfig><dir>%s/fonts</dir></fontconfig>' "$PWD" > /tmp/fonts.conf
PYTHONPATH=/tmp/pylibs python3 print/build.py
```

`rsvg-convert` (brew) рисует PDF и PNG; шрифты подключаются через `FONTCONFIG_FILE`,
чтобы не зависеть от системных. Проверка QR после правок:

```bash
PYTHONPATH=/tmp/pylibs python3 -c "
import cv2; print(cv2.QRCodeDetector().detectAndDecode(cv2.imread('preview/card-back-300dpi.png'))[0])"
# ожидается https://pseudex.ru/i/igor
```

Плашки на лицевой стороне считаются по длине реального значения из `PEOPLE` — руками
их двигать нельзя, разъедутся со строкой.
