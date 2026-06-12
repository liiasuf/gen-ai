# Домашнее задание к Семинару 4: RAG на собственном корпусе — сравнение двух стратегий чанкинга

## 1. Корпус

Корпус — 10 авторских текстов о подготовке к экзамену **IELTS Academic** (структура теста, секции Listening/Reading/Writing/Speaking, система баллов, академическая лексика и парафраз, практические советы на день экзамена, примеры заданий с разбором), суммарно **41 788 символов** (~6 470 слов), файлы лежат в `data/doc_1_overview.txt` … `data/doc_10_sample_questions.txt`.

| Файл | Тема |
|---|---|
| doc_1_overview | Общая структура теста, тайминг, 4 секции |
| doc_2_listening | Listening: формат, 40 вопросов, типы заданий |
| doc_3_reading | Reading: 3 текста, 40 вопросов, True/False/Not Given |
| doc_4_writing_task1 | Writing Task 1: графики, диаграммы, 150 слов |
| doc_5_writing_task2 | Writing Task 2: эссе, 250 слов, критерии оценки |
| doc_6_speaking | Speaking: 3 части, 11–14 минут, критерии оценки |
| doc_7_band_scores | Шкала баллов 0–9, расчёт Overall Band Score |
| doc_8_vocabulary | Академическая лексика, техники парафраза |
| doc_9_test_day | Документы, правила, советы на день экзамена |
| doc_10_sample_questions | Примеры заданий Reading/Listening с разбором |

Так как тексты написаны на английском (тематика — IELTS Academic), вопросы gold-сета также на английском, чтобы избежать кросс-языковой просадки ретривера.

## 2. Gold-разметка (12 вопросов)

| id | type | question | gold_sources | сложный? |
|---|---|---|---|---|
| 1 | прямой | How many questions are there in total in the IELTS Academic Listening section? | doc_2 | |
| 2 | прямой | What is the minimum word count required for IELTS Academic Writing Task 2? | doc_5 | |
| 3 | точный артикул | In Reading True/False/Not Given questions, what does the answer 'NOT GIVEN' mean? | doc_3 | |
| 4 | синоним | What overall score do most universities require for admission to an undergraduate program? | doc_7 | |
| 5 | перефраз | How can a candidate avoid repeating the same words over and over in their essay? | doc_8 | |
| 6 | multi-hop | How long does the entire IELTS Academic test take from Listening through Speaking, and how many total questions are there across Listening and Reading combined? | doc_1, doc_2, doc_3 | ✅ |
| 7 | multi-hop | Which assessment criteria are shared between the Speaking test and Writing Task 2? | doc_5, doc_6 | ✅ |
| 8 | прямой | How many parts does the Speaking test have, and how long does the whole test last? | doc_6 | |
| 9 | прямой | What types of visual information can appear in Writing Task 1? | doc_4 | |
| 10 | синоним | What identification do candidates need to bring with them on exam day? | doc_9 | |
| 11 | прямой | How is the Overall Band Score calculated from the four section scores? | doc_7 | |
| 12 | multi-hop / перефраз | If someone's four section scores average to 6.75, what overall score would they get, and which four skill sections are averaged to produce that number? | doc_7, doc_1 | ✅ |

Сложные вопросы — №6, №7, №12 (multi-hop: ответ требует информации из 2–3 разных документов). №4, №5, №10 используют синонимы/перефразирование терминов корпуса ("overall score" vs "Overall Band Score", "avoid repeating words" vs "paraphrasing", "identification" vs "identification document").

## 3. Пайплайн и стратегии чанкинга

Код — `pipeline.py`. Используются две стратегии:

- **A (fixed-size)** — `text[i:i+2000]`, шаг 2000 символов, без перекрытия. На корпусе получилось **28 чанков**, средняя длина **1492 символа**.
- **B (recursive)** — рекурсивный сплиттер в духе `RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=80)`, сепараторы `["\n\n", "\n", ". ", " ", ""]`. Получилось **151 чанк**, средняя длина **284 символа**.

**Про эмбеддинги (важная оговорка):** в задании предложен `sentence-transformers`, но в данной песочнице установка `sentence-transformers` требует загрузки `torch` (~430 МБ), что не укладывается в доступный лимит времени на установку. Поэтому ретривер реализован на **TF-IDF + косинусная близость (scikit-learn)** — это полноценная замена эмбеддингов для сравнения чанкинга, так как обе стратегии прогоняются через один и тот же ретривер: разница в hit-rate обусловлена именно границами чанков, а не выбором эмбеддера.

## 4. Результаты hit-rate@5

| Стратегия | Чанков | Средняя длина чанка | hit-rate@5 (хотя бы один gold-документ в топ-5) | hit-rate@5 (все gold-документы в топ-5, строго для multi-hop) |
|---|---|---|---|---|
| A — fixed-size (2000, без overlap) | 28 | 1492 симв. | **1.000** (12/12) | **0.917** (11/12) |
| B — recursive (400/80) | 151 | 284 симв. | **1.000** (12/12) | **0.833** (10/12) |

Базовый hit-rate@5 («хотя бы один из gold-источников попал в топ-5») получился **1.000 для обеих стратегий** — корпус из 10 документов слишком мал относительно k=5 (топ-5 покрывает половину всех документов), поэтому эта метрика на нём не различает стратегии («работает из коробки», как и предупреждалось в задании).

Для содержательного сравнения добавлена более строгая метрика — для multi-hop вопросов (№6, 7, 12) проверяется, что **все** gold-документы попали в топ-5. По этой метрике стратегия A (fixed-size) обходит B (recursive): 11/12 против 10/12. Разница приходится на вопрос №7.

## 5. Анализ ошибок

**Вопрос №7** ("Which assessment criteria are shared between the Speaking test and Writing Task 2?", gold = doc_5 + doc_6):
- **Fixed-size**: топ-5 = `doc_5_c0, doc_4_c0, doc_6_c0, doc_1_c0, doc_5_c1` — оба gold-документа присутствуют. Крупный чанк `doc_6_c0` (~2000 симв.) включает в себя сразу описание частей Speaking-теста *и* список из 4 критериев оценки (Fluency and Coherence, Lexical Resource, Grammatical Range and Accuracy, Pronunciation), поэтому он хорошо матчится по словам "assessment criteria".
- **Recursive**: топ-5 = `doc_7_c2, doc_5_c0, doc_8_c0, doc_4_c0, doc_5_c6` — doc_5 есть, **doc_6 отсутствует**. При чанках по 400 символов абзац про критерии оценки Speaking оказался в отдельном небольшом чанке `doc_6`, который по TF-IDF набрал меньше очков, чем чанки из doc_7 (про шкалу баллов) и doc_8 (про лексику) — у тех тоже встречаются слова "criteria"/"assessed", и из-за мелкой гранулярности они конкурируют за топ-5 наравне с релевантным, но не попадают туда.
- **Вывод по этому вопросу**: крупные чанки fixed-size "склеивают" вместе несколько связанных фактов одного документа в один чанк, что помогает multi-hop вопросам, требующим всех gold-источников — у recursive же релевантный, но узкий по теме чанк doc_6 теряется среди множества мелких конкурентов.

**Вопрос №6** ("How long does the entire IELTS Academic test take… and how many total questions are there across Listening and Reading combined?", gold = doc_1 + doc_2 + doc_3):
- **Обе стратегии** не подтягивают `doc_3` (Reading) в топ-5: fixed получает `doc_1, doc_2, doc_6, doc_7, doc_9`, recursive — `doc_1 (x2), doc_2, doc_9, doc_6`. Вопрос явно упоминает "Listening" и "Reading", но doc_1 (Overview) уже содержит фразу "40 questions in Listening and 40 questions in Reading", поэтому именно doc_1 и doc_2 перетягивают релевантность, а doc_3 (где подробно описан Reading) остаётся за бортом.
- Это пример ограничения **самого ретривера** (TF-IDF), а не чанкинга: проблема не решается ни одной из двух стратегий, потому что слово "Reading" уже "обслужено" чанком из doc_1, и TF-IDF не различает, что doc_3 даёт *дополнительную*, а не дублирующую информацию.

**Вопрос №12** (multi-hop/перефраз про округление Overall Band Score, gold = doc_7 + doc_1):
- Оба чанкинга успешно находят оба документа (fixed: `doc_7, doc_1, doc_7, doc_2, doc_1`; recursive: `doc_7, doc_1, doc_7, doc_7, doc_7`) — здесь оба справляются, так как doc_1 короткий по теме "четыре секции" и легко попадает в чанк целиком при любой гранулярности.

## 6. Вывод

На базовой метрике hit-rate@5 («хотя бы один источник в топ-5») обе стратегии чанкинга показали одинаковый результат (1.0) — корпус из 10 документов оказался слишком мал, чтобы эта метрика была информативной. На более строгой метрике для multi-hop вопросов («все gold-источники в топ-5») **fixed-size чанкинг (2000 симв., без overlap) выиграл** у recursive (400/80) — 0.917 против 0.833. Причина в том, что крупные чанки fixed-size объединяют несколько смежных фактов одного документа в единый блок текста, что облегчает их извлечение по multi-hop запросам, требующим сразу нескольких фактов из одного документа; recursive же дробит документ на много мелких тематических кусков, и часть из них "теряет" конкуренцию за топ-5 даже при общей релевантности документа.
