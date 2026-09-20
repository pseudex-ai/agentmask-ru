# AgentMask-RU — таблица

Корпус `af8011b7bb815ae9`, 272 случаев. В скобках — точный 95% интервал Клоппера–Пирсона.
Столбцы НЕ складываются в общий балл: шлюз, который маскирует всё, выигрывает первый
столбец и проигрывает два последних.

| система | скрыто | скрыто целиком | круг (из скрытых) | круг (из всех) | не тронуто лишнего | одна подстановка | ошибок |
|---|---|---|---|---|---|---|---|
| cloudru | 43.7% [40–47] 297/680 | 42.8% [39–47] 291/680 | 100.0% [99–100] 247/247 | 100.0% [99–100] 536/536 | 100.0% [99–100] 624/624 | 22.2% [3–60] 2/9 | 0 |
| litellm | 63.8% [60–67] 434/680 | 46.0% [42–50] 313/680 | 0.0% [0–1] 0/327 | 36.8% [33–41] 190/517 | 70.0% [66–74] 437/624 | 0.0% [0–12] 0/29 | 0 |
| llm_guard | 42.6% [39–46] 290/680 | 34.9% [31–39] 237/680 | 99.5% [97–100] 188/189 | 99.8% [99–100] 535/536 | 96.8% [95–98] 604/624 | 8.9% [2–21] 4/45 | 0 |
| noop | 0.0% [0–1] 0/680 | 0.0% [0–1] 0/680 | — | 100.0% [99–100] 536/536 | 100.0% [99–100] 624/624 | — | 0 |
| placeholder_regex | 53.1% [49–57] 361/680 | 51.5% [48–55] 350/680 | 98.0% [96–99] 287/293 | 98.9% [98–100] 518/524 | 79.8% [76–83] 498/624 | 26.7% [8–55] 4/15 | 0 |
| presidio | 58.1% [54–62] 395/680 | 50.4% [47–54] 343/680 | 90.8% [87–94] 277/305 | 94.7% [92–96] 503/531 | 72.0% [68–75] 449/624 | 46.8% [32–62] 22/47 | 0 |
| pseudex | 94.4% [92–96] 642/680 | 79.3% [76–82] 539/680 | 79.5% [76–83] 388/488 | 80.2% [76–84] 405/505 | 98.2% [97–99] 613/624 | 63.0% [48–77] 29/46 | 0 |

## Парные сравнения (McNemar, точный)

| пара | строка | b | c | p |
|---|---|---|---|---|
| cloudru ↔ litellm | leak | 36 | 173 | 0.000 |
| cloudru ↔ litellm | end_to_end | 327 | 0 | 0.000 |
| cloudru ↔ llm_guard | leak | 155 | 148 | 0.730 |
| cloudru ↔ llm_guard | end_to_end | 1 | 0 | 1.000 |
| cloudru ↔ noop | leak | 297 | 0 | 0.000 |
| cloudru ↔ noop | end_to_end | 0 | 0 | 1.000 |
| cloudru ↔ placeholder_regex | leak | 17 | 81 | 0.000 |
| cloudru ↔ placeholder_regex | end_to_end | 6 | 0 | 0.031 |
| cloudru ↔ presidio | leak | 133 | 231 | 0.000 |
| cloudru ↔ presidio | end_to_end | 28 | 0 | 0.000 |
| cloudru ↔ pseudex | leak | 0 | 345 | 0.000 |
| cloudru ↔ pseudex | end_to_end | 100 | 0 | 0.000 |
| litellm ↔ llm_guard | leak | 248 | 104 | 0.000 |
| litellm ↔ llm_guard | end_to_end | 1 | 327 | 0.000 |
| litellm ↔ noop | leak | 434 | 0 | 0.000 |
| litellm ↔ noop | end_to_end | 0 | 327 | 0.000 |
| litellm ↔ placeholder_regex | leak | 128 | 55 | 0.000 |
| litellm ↔ placeholder_regex | end_to_end | 4 | 323 | 0.000 |
| litellm ↔ presidio | leak | 171 | 132 | 0.029 |
| litellm ↔ presidio | end_to_end | 20 | 318 | 0.000 |
| litellm ↔ pseudex | leak | 5 | 213 | 0.000 |
| litellm ↔ pseudex | end_to_end | 54 | 276 | 0.000 |
| llm_guard ↔ noop | leak | 290 | 0 | 0.000 |
| llm_guard ↔ noop | end_to_end | 0 | 1 | 1.000 |
| llm_guard ↔ placeholder_regex | leak | 117 | 188 | 0.000 |
| llm_guard ↔ placeholder_regex | end_to_end | 6 | 1 | 0.125 |
| llm_guard ↔ presidio | leak | 52 | 157 | 0.000 |
| llm_guard ↔ presidio | end_to_end | 27 | 0 | 0.000 |
| llm_guard ↔ pseudex | leak | 20 | 372 | 0.000 |
| llm_guard ↔ pseudex | end_to_end | 100 | 1 | 0.000 |
| noop ↔ placeholder_regex | leak | 0 | 361 | 0.000 |
| noop ↔ placeholder_regex | end_to_end | 6 | 0 | 0.031 |
| noop ↔ presidio | leak | 0 | 395 | 0.000 |
| noop ↔ presidio | end_to_end | 28 | 0 | 0.000 |
| noop ↔ pseudex | leak | 0 | 642 | 0.000 |
| noop ↔ pseudex | end_to_end | 100 | 0 | 0.000 |
| placeholder_regex ↔ presidio | leak | 131 | 165 | 0.055 |
| placeholder_regex ↔ presidio | end_to_end | 28 | 6 | 0.000 |
| placeholder_regex ↔ pseudex | leak | 0 | 281 | 0.000 |
| placeholder_regex ↔ pseudex | end_to_end | 95 | 3 | 0.000 |
| presidio ↔ pseudex | leak | 18 | 265 | 0.000 |
| presidio ↔ pseudex | end_to_end | 93 | 21 | 0.000 |

