#!/bin/sh
# Пересобирает макет и складывает ДВА архива:
#
#   PSEUDEX-tipografiya.zip  — ЧИСТО для типографии, 4 файла печати и ТЗ
#   PSEUDEX-vizitki.zip      — внутреннее: брендбук, страницы, исходники
#
# Почему скрипт, а не «собрал один раз руками»: телефон и почта на визитке
# поменяются ещё не раз, а архивы после каждой правки должны пересобираться
# целиком — иначе цех получает PDF с новым номером и превью со старым.
#
# ГЛАВНОЕ ПРО АРХИВ ДЛЯ ЦЕХА: он устроен так, чтобы человек, открывший его
# впервые, не спрашивал «что тут что». На верхнем уровне пять записей, а не
# сорок: что делать, задание, картинка, папка печати и папка «обычно не нужно».
#   sh pack.sh                  -> ~/Downloads/PSEUDEX-*.zip
set -e
cd "$(dirname "$0")"

DEST="${1:-$HOME/Downloads}"
DIST="otgruzka/PSEUDEX-vizitki"
PRINT="$DIST/dlya-tipografii"
INNER="$DIST/vnutrennee"

PYTHONPATH="${PYTHONPATH:-/tmp/pylibs}" python3 print/build.py
PYTHONPATH="${PYTHONPATH:-/tmp/pylibs}" python3 team/build-pages.py

rm -rf otgruzka
mkdir -p "$PRINT/pechatat" "$PRINT/ostalnoe/bez-vyletov" "$PRINT/ostalnoe/300dpi" \
         "$PRINT/ostalnoe/shrifty" "$PRINT/ostalnoe/plastik-s-nfc" \
         "$INNER/nfc" "$INNER/istochniki-maketa" "$INNER/preview"

# --- то, что уходит цеху ------------------------------------------------------
# На верхнем уровне — только то, что реально нужно. Всё, что «может
# понадобиться, если попросят», убрано в ostalnoe/: сорок файлов в корне
# читаются как «тут что-то важное, но непонятно что».
for s in igor gosha slava; do
  cp "print/card-front-$s-paper.pdf" "$PRINT/pechatat/$s-front.pdf"
  cp "print/card-back-$s-paper.pdf"  "$PRINT/pechatat/$s-back.pdf"
  cp "print/card-front-$s-paper-90x50.pdf" "$PRINT/ostalnoe/bez-vyletov/$s-front-90x50.pdf"
  cp "print/card-back-$s-paper-90x50.pdf"  "$PRINT/ostalnoe/bez-vyletov/$s-back-90x50.pdf"
  cp "preview/card-front-$s-paper-90x50-300dpi.png" "$PRINT/ostalnoe/300dpi/$s-front.png"
  cp "preview/card-back-$s-paper-90x50-300dpi.png"  "$PRINT/ostalnoe/300dpi/$s-back.png"
  cp "print/spot-uv-mask-$s-paper.pdf" "$PRINT/ostalnoe/plastik-s-nfc/lak-maska-$s.pdf"
  cp "print/card-front-$s-plastic.pdf" print/card-back-$s-plastic.pdf \
     print/card-front-$s-plastic-85x54.pdf print/card-back-$s-plastic-85x54.pdf \
     "$PRINT/ostalnoe/plastik-s-nfc/"
done
cp preview/card-mockup-paper.png "$PRINT/02-kak-vyglyadit.png"
cp fonts/Inter-*.ttf fonts/JetBrainsMono-*.ttf \
   fonts/LICENSE-Inter.txt fonts/LICENSE-JetBrainsMono.txt "$PRINT/ostalnoe/shrifty/"

cat > "$PRINT/00-CHTO-DELAT.txt" <<'TXT'
ЧТО ДЕЛАТЬ
==========

1. Печатать четыре файла из папки  pechatat/  — по два на человека:
       igor-front.pdf    лицевая сторона, Игорь
       igor-back.pdf     оборотная, Игорь
       gosha-front.pdf   лицевая, Георгий
       gosha-back.pdf    оборотная, Георгий
2. Прочитать  01-ZADANIE.txt  — там изделие, бумага, ламинация, бюджет
   и то, что просим подтвердить при заказе.
3. Посмотреть  02-kak-vyglyadit.png  — как это выглядит в сборе.

ПАПКА ostalnoe/ — ОБЫЧНО НЕ НУЖНА
    bez-vyletov/   те же файлы ровно 90 x 50, без вылетов
    300dpi/        растровые PNG, если нужен растр, а не PDF
    shrifty/       шрифты Inter и JetBrains Mono (SIL OFL, печать разрешена)
    plastik-s-nfc/ ОТЛОЖЕНО: вариант для пластика с NFC-чипом и маска под лак

ГЛАВНОЕ
    QR-код впечатывается навсегда. Адрес, на который он ведёт, должен быть
    живым до печати тиража.
TXT

cat > "$PRINT/01-ZADANIE.txt" <<'TXT'
ТЕХНИЧЕСКОЕ ЗАДАНИЕ: визитки на бумаге
======================================

БЮДЖЕТ: до 5000 ₽ на весь тираж. Просьба предложить ВАРИАНТ ПОД ЭТУ СУММУ,
а не прайс вообще: сколько визиток в неё укладывается и что входит в цену.
Если вариант дороже — так и скажите, будем решать.

ИЗДЕЛИЕ
  Формат .......... 90 x 50 мм (стандартный бумажный, НЕ карточный)
  Бумага .......... плотная, 300 г/м² или плотнее — карточка не должна гнуться
  Печать .......... полноцвет 4+4, весь фон залит в край, белого канта быть не должно
  Ламинация ....... МАТОВАЯ, с двух сторон обязательно
  Тираж ........... предложите сами под бюджет

ФАЙЛЫ ПЕЧАТИ (папка pechatat/)
  Печатать четыре файла, по два на человека:
    igor-front.pdf  + igor-back.pdf    Игорь
    gosha-front.pdf + gosha-back.pdf   Георгий
  Размер 94 x 54 мм — это 90 x 50 ПЛЮС 2 мм вылета с каждой стороны.
  В папке ostalnoe/bez-vyletov/ те же макеты ровно 90 x 50, если вам удобнее
  без вылетов. Тираж на каждого человека назовите отдельно.

ПРОЧЕЕ
  В PDF шрифты внедрены. Нужны сами шрифты — папка ostalnoe/shrifty/,
  обе лицензии SIL OFL, коммерческая печать разрешена.

ПРОСЬБА ПОДТВЕРДИТЬ ПРИ ЗАКАЗЕ
  1. Срок изготовления — изделие нужно к четвергу 8 октября.
  2. Цену за тираж, по каждому человеку отдельно.
  3. Что будет прислано фото ОДНОЙ готовой визитки до печати тиража.
  4. Что QR-код на пробной визитке читается с телефона.
  5. Если макет нужно перевести в кривые — скажите, пришлём.
TXT

cat > "$PRINT/ostalnoe/plastik-s-nfc/00-otlozheno.txt" <<'TXT'
ОТЛОЖЕНО, НЕ ПЕЧАТАТЬ.

Это тот же макет в карточном размере 85.6 x 54 мм для пластика PVC 0.76 мм
с NFC-чипом внутри. Он собран заранее на случай возврата к пластику.

  card-front-<имя>-plastic.pdf       89.6 x 58 мм (карта + 2 мм вылета)
  card-front-<имя>-plastic-85x54.pdf ровно 85.6 x 54 мм
  lak-maska-<имя>.pdf                маска под выборочный лак
TXT

# --- внутреннее: не для цеха --------------------------------------------------
cp BRANDBOOK.md CHATGPT-PROMPT.md PRINT-SHORTLIST.md README.md "$INNER/"
cp nfc/card-*.html nfc/team.html nfc/*.vcf "$INNER/nfc/"
cp print/build.py print/variants.py print/*.svg "$INNER/istochniki-maketa/"
cp preview/card-mockup-paper.png preview/card-mockup-plastic.png "$INNER/preview/"

cat > "$DIST/00-CHTO-ETO.txt" <<'TXT'
PSEUDEX — визитки. Что в архиве.
================================

Два архива, и это разные вещи:

  PSEUDEX-tipografiya.zip   то, что отправляется цеху. Открывать и печатать.
  PSEUDEX-vizitki.zip       этот архив. Внутреннее: брендбук, промты, страницы
                            команды, исходники макета. Цеху не нужно.

Что печатать — написано в  dlya-tipografii/00-CHTO-DELAT.txt
TXT

# --- архивы -------------------------------------------------------------------
mkdir -p "$DEST"
rm -f "$DEST/PSEUDEX-vizitki.zip" "$DEST/PSEUDEX-tipografiya.zip"
( cd otgruzka && zip -qrX "$DEST/PSEUDEX-vizitki.zip" PSEUDEX-vizitki -x '.*' -x '*/.*' )

STAGE="otgruzka/tipografiya"
mkdir -p "$STAGE"
cp -R "$PRINT/." "$STAGE/"
mv "$STAGE" "otgruzka/PSEUDEX-tipografiya"
( cd otgruzka && zip -qrX "$DEST/PSEUDEX-tipografiya.zip" PSEUDEX-tipografiya -x '.*' -x '*/.*' )

echo
echo "для типографии: $DEST/PSEUDEX-tipografiya.zip  ($(du -h "$DEST/PSEUDEX-tipografiya.zip" | cut -f1), $(find "$PRINT" -type f | wc -l | tr -d ' ') файлов)"
echo "внутренний:     $DEST/PSEUDEX-vizitki.zip      ($(du -h "$DEST/PSEUDEX-vizitki.zip" | cut -f1), $(find otgruzka/PSEUDEX-vizitki -type f | wc -l | tr -d ' ') файлов)"
