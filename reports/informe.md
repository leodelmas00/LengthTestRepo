# Informe de control de longitud

**Modelo:** Mistral-Small-3.2-24B-Instruct-2506 · **Temperatura:** 0 · **Sin memoria** · **n=100 por celda**

**Baseline de referencia:** `combinaciones` (instrucción numérica estándar con guardrail). `baseline__base` (BASE sola) produce ~61.7 palabras de media pero no tiene ventana, por lo que no se usa para comparar % en ventana.

**Ventanas:** short `[30, 60]` (objetivo 45) · long `[140, 200]` (objetivo 170).

---

## 1. Técnicas evaluadas

| Técnica (grupo) | Definición breve |
|---|---|
| Baseline (`baseline`) | Respuesta sin módulos de longitud ni formalidad (solo `BASE`). Condición de control. |
| Aislados (`aislados`) | Cada módulo por separado: solo longitud corta, solo longitud larga, solo formalidad formal, solo formalidad informal. |
| Combinaciones (`combinaciones`) | Longitud y formalidad juntas; evalúa si ambos parámetros se afectan entre sí. |
| Over-asking (`over_asking`) | Pide un objetivo de palabras mayor al deseado para compensar la subproducción; se calcula un factor de corrección por celda. |
| Unidad alternativa A (`unidad_a - sentences`) | Reemplaza el conteo de palabras por oraciones, que el modelo controla mejor. |
| Unidad alternativa B (`unidad_b - paragraphs`) | Reemplaza el conteo de palabras por párrafos y oraciones. |
| Desacople del informal (`desacople_informal`) | Reescribe el módulo informal quitando las señales de brevedad ("just replying", "texting a friend"); evalúa si la subproducción en informal+larga desaparece. |
| One-shot (`one_shot`) | Agrega 1 ejemplo del largo/registro objetivo, sobre otro tema, para anclar la longitud por imitación. |
| Few-shot (`few_shot`) | Igual que one-shot pero con 3 ejemplos. |
| Retry concreto (`retry_concrete`) | Un verificador externo cuenta las palabras; si está fuera de ventana, devuelve conteo + rango + dirección y regenera (máx. 2 reintentos). Self-Refine con el conteo hecho en código. |
| Retry genérico (`retry_generic`) | Mismo bucle, feedback solo con dirección ("muy corta"/"muy larga"), sin cifras. Sirve de control. |
| Metropolis-Hastings (`retry_mh`) | Muestreo iterativo con aceptación/rechazo y juez; corrige la longitud sin modificar el modelo; hasta 5 rondas. |
| Countdown / CAPEL (`countdown`) | El modelo escribe una cuenta regresiva con un marcador antes de cada palabra para "contar en voz alta"; una sola llamada; luego se borran los marcadores. |

---

## 2. Prompts base y ensamblado

El system prompt se arma concatenando módulos en este orden fijo (el guardrail se agrega **siempre**, incluso en baseline y aislados):

```
BASE → [LENGTH MODULE] → [FORMALITY MODULE] → GUARDRAIL → [EXAMPLE MODULE]
```

- `USER_PROMPT` (fijo): `Hi, can you book me a flight from Buenos Aires to Mexico?`
- `BASE`: `You are a conversational assistant answering user queries about travel planning. Respond in English.`
- `LENGTH MODULE - short`: `Respond in between 30 and 60 words total; aim for approximately 45 words. Do not add information beyond what is strictly requested, even if other modules suggest further development.`
- `LENGTH MODULE - long`: `Respond in between 140 and 200 words total; aim for approximately 170 words. Develop the topic in depth with examples where applicable.`
- `FORMALITY MODULE - formal`: `write out every word in full (use "do not" and "it is" in their complete forms). Use precise terminology, careful syntax, and impersonal or third-person constructions throughout. Maintain an elevated, professional tone in every sentence. long level only: A formal answer here is economical, not padded: make your point in no more than 9 sentences and stop.`
- `FORMALITY MODULE - informal`: `contractions ('don't', 'it's'), everyday vocabulary, second-person address ('you'). Avoid unnecessary technical terms when a common equivalent exists. Allowed: moderate interjections ('sure', 'look'). You are texting a friend back. Not advising them, not helping them - just replying. Speak from your own experience: say what you did or what you'd do, never what "one can" or "you should" do.`

`ANTI-INTERFERENCE GUARDRAIL` (siempre presente):

```
The 2 dimensions (length, formality) are INDEPENDENT. Satisfy BOTH SIMULTANEOUSLY without one relaxing the other. Specifically:
- A short response can be fully informal without exceeding the word limit.
- A formal response can be short.
- A long response reaches the SAME word count in either register.
Casual phrasing is not a reason to finish early, and formal phrasing is not a reason to run past the limit. Hit the stated target either way.
- Register never justifies going over or under the word count, and the word count never justifies dropping the register.
Before responding, verify internally that both conditions are met.
```

---

## 3. Modificaciones por técnica

### Over-asking (sobre-solicitud)
Reemplaza el `LENGTH MODULE` por una versión con objetivo mayor al deseado (se evalúa contra la ventana real):

- short: `Respond in between 60 and 90 words total; aim for approximately 75 words. Do not add information beyond what is strictly requested, even if other modules suggest further development.`
- long: `Respond in between 200 and 260 words total; aim for approximately 230 words. Develop the topic in depth with examples where applicable.`

### Unidad de medida alternativa A (oraciones)
- short (3 × ~15): `Respond in exactly 3 sentences, each of about 15 words. Write them as continuous prose, with no lists. Do not add information beyond what is strictly requested. Count your sentences before responding.`
- long (9-10 × ~18): `Respond in exactly 9 to 10 sentences, each of about 18 words. Write them as continuous prose, with no lists. Develop the topic in depth with examples where applicable. Count your sentences before responding.`

### Unidad de medida alternativa B (párrafos)
- short (2 × 2 × ~11): `Respond in exactly 2 paragraphs of 2 sentences each. Each sentence should be about 11 words long. Do not add information beyond what is strictly requested. Count your paragraphs and sentences before responding.`
- long (3 × 3 × ~18): `Respond in exactly 3 paragraphs of 3 sentences each. Each sentence should be about 18 words long. Develop the topic in depth with examples where applicable. Count your paragraphs and sentences before responding.`

### Desacople del módulo informal respecto de la brevedad
Reemplaza `FORMALITY MODULE - informal` (sin "just replying" ni "texting a friend"):

`Use an informal register: contractions ("don't", "it's"), everyday vocabulary, and second-person address ("you"). Avoid technical terms when a common equivalent exists. Moderate interjections ("sure", "look") are allowed. Speak from your own experience: say what you did or what you'd do, never what "one can" or "you should" do. Informal does not mean short. Share details, small stories and specific tips, and develop each point fully, the way you would in a long, friendly voice message. Sentence structure is free: write complete, flowing sentences.`

### Ejemplos por celda (one-shot / few-shot)
Se agrega un `EXAMPLE MODULE` al final del system prompt (después del guardrail). Los ejemplos vienen de `few_shot_bank.json` (24 ejemplos = 6 situaciones × 4 celdas short/long × formal/informal; ~40 palabras en short y ~170 en long). one-shot usa 1 ejemplo (`hotel_lisbon`); few-shot usa 3 (`hotel_lisbon`, `lost_luggage`, `travel_insurance_japan`).

`EXAMPLE MODULE` (header): `Here is an example of the expected length and register. It covers a different topic: match its length and style, not its content.`

Estructura por ejemplo:

```
[Example 1]
User: <pregunta del banco>
Assistant: <respuesta del banco>
```

### Reintento con feedback concreto
Si la respuesta queda fuera de ventana, se continúa la conversación (`system` → `user` → `assistant` → `user` feedback) y se regenera. Máx. 2 reintentos. Valores: short `LO=30, HI=60, TARGET=45`; long `LO=140, HI=200, TARGET=170`.

- Demasiado corta: `Your response has {N} words. The required length is between {LO} and {HI} words (aim for about {TARGET}). Rewrite your previous response, expanding it with more detail and examples until it reaches about {TARGET} words. Keep the same register. Reply only with the new response, without comments.`
- Demasiado larga: `Your response has {N} words. The required length is between {LO} and {HI} words (aim for about {TARGET}). Rewrite your previous response, shortening it by removing secondary details until it reaches about {TARGET} words. Keep the same register. Reply only with the new response, without comments.`

### Reintento con feedback genérico (sin cifras)
Mismo bucle, feedback solo con dirección:

- Demasiado corta: `Your response is too short. Rewrite it so that it is longer. Keep the same register. Reply only with the new response, without comments.`
- Demasiado larga: `Your response is too long. Rewrite it so that it is shorter. Keep the same register. Reply only with the new response, without comments.`

### Metropolis-Hastings con muestreo de importancia
Bucle iterativo (hasta 5 rondas): genera la respuesta inicial; si está fuera de ventana pide una revisión; si la candidata cae dentro de la ventana se acepta **sin consultar al juez**; si sigue fuera, un juez (el mismo Mistral) puntúa candidata vs anterior y el código calcula `ratio = (dist_prev / dist_cand) × (score_cand / score_prev)`. Se acepta la candidata si `ratio ≥ 1`; si no, se rechaza y el bucle corta (con temperatura 0 la siguiente propuesta sería casi idéntica).

`REVISION FEEDBACK` lejos de la ventana (>3 palabras):

- Demasiado corta: `The generated answer is too short at {N} words. Please improve it to be about {TARGET} words by adding some relevant details and examples. Keep the same register. Reply only with the new response.`
- Demasiado larga: `The generated answer is too long at {N} words. Please improve it to be about {TARGET} words by focusing on the core ideas and removing secondary details. Keep the same register. Reply only with the new response.`

`REVISION FEEDBACK` cerca (≤3 palabras): `The generated answer is too {short|long} at {N} words. Please {add|delete} {D+5} words appropriately based on the previous response. Keep the same register. Reply only with the new response.` (`D` = distancia al borde más cercano).

`JUDGE MODULE` (llamada aparte, mismo modelo):

```
[SYSTEM]: You are a powerful evaluator for travel assistant responses.
[USER]: Compare two responses to the same user message. Score each response from 1 to 10 on each criterion: helpfulness, relevance, accuracy, {level of detail | conciseness}, and register adherence. Register adherence means the response must be {REGISTER}. Avoid position biases and ensure that the order in which the responses were presented does not influence your decision.
User message: {x}
Response 1: {candidata}
Response 2: {anterior}
Output only JSON: {"score_1": <sum of criteria>, "score_2": <sum of criteria>}
```

### Countdown prompting (CAPEL)
Reemplaza la parte numérica del `LENGTH MODULE` (se conserva la instrucción no numérica: "Develop the topic in depth…" en long y "Do not add information…" en short). `{N}` = 170 (long) / 45 (short). Una sola llamada, sin bucle ni juez.

```
Required output format:
1. For each integer k from {N} down to 1: print the marker <k>, then immediately append one English word (letters with optional leading/trailing punctuation, such as comma, period, apostrophe or hyphen). No spaces inside this token.
2. After the word paired with <1>, write <0> and stop generating.
3. Markers and punctuation are not counted toward the {N}-word total; only the English words count.
4. If you risk running short, add fresh, meaningful prose; do not end with bare markers.

Rules:
- Produce exactly {N} markers (<{N}> … <1>) and exactly {N} words.
- The numbers in successive markers must decrease by 1, with no skips or repeats.
- Two markers may never appear back to back without a word between them.
- No extra text after <0>.
- A token may include a trailing newline (\n) to represent a line break.

Correct example (N = 5): <5>Hello,<4>world!<3>How's<2>everything?<1>Great.<0>
```

Limpieza antes de contar: `re.sub(r'<\d+>', ' ', texto).strip()`, luego `len(texto.split())` como en el resto.

---

## 4. Respaldo en la literatura

Retkowski y Waibel (2025), *Zero-Shot Strategies for Length-Controllable Summarization* (arXiv:2501.00233), estudian el control de longitud sin ajustar parámetros (Llama-3-8B-Instruct). Sus resultados respaldan dos técnicas implementadas:

- **Over-asking:** el modelo se desvía de forma sistemática (se queda corto en targets largos) y ajustar el número pedido corrige el sesgo; el factor debe calibrarse por celda.
- **Retry con feedback concreto:** informar cuántas palabras tiene la respuesta y cuánto se desvió mejora el cumplimiento, y la mejora continúa a lo largo de las rondas.

El paper no evalúa la combinación de ambas ni usa un modelo de chat, por lo que sus cifras sirven de respaldo del mecanismo y no como valores esperados en estas celdas.

CAPEL (countdown) corresponde a *Prompt-Based One-Shot Exact Length-Controlled Generation with LLMs* (arXiv:2508.13805); el marco de Metropolis-Hastings corresponde a *Length Controlled Generation for Black-Box Large Language Models* (arXiv:2412.14656).

---

## 5. Métodos no aplicables

- **`max_tokens` (API):** limita el máximo de tokens generados, pero corta el texto a mitad de frase en lugar de producir un final coherente.
- **Fine-tuning / decodificación interna:** técnicas como LDPE (*Precise Length Control in Large Language Models*), HANSEL (*Hansel: Output Length Controlling Framework*) y CIE (*Controlling Language Model Text Generations Using Continuous Control Vectors*) requieren modificar pesos o el mecanismo de decodificación; no aplican aquí porque el modelo se usa como caja negra vía API.

---

## 6. Datos clave por técnica y celda

| Técnica | Celda | % en ventana | Media | Desvío |
|---|---|---|---|---|
| baseline (BASE sola) | — | — | 61.7 | 12.8 |
| aislados | solo short | 22 | 22.1 | 5.9 |
| aislados | solo long | 16 | 115.3 | 26.0 |
| aislados | solo formal | — | 83.5 | 7.4 |
| aislados | solo informal | — | 31.4 | 8.2 |
| combinaciones (naive) | short+formal | 99 | 36.0 | 3.6 |
| combinaciones (naive) | short+informal | **0** | 21.2 | 2.3 |
| combinaciones (naive) | long+formal | **0** | 116.9 | 10.0 |
| combinaciones (naive) | long+informal | **0** | 69.0 | 7.5 |
| over_asking | short+formal | 81 | 60.2 | 4.9 |
| over_asking | short+informal | 39 | 30.9 | 5.1 |
| over_asking | long+formal | 15 | 132.3 | 9.9 |
| over_asking | long+informal | 0 | 91.5 | 10.9 |
| unidad_a - sentences | short+formal | 100 | 37.4 | 1.5 |
| unidad_a - sentences | short+informal | 82 | 31.9 | 4.6 |
| unidad_a - sentences | long+formal | 34 | 133.8 | 12.9 |
| unidad_a - sentences | long+informal | 5 | 109.3 | 14.3 |
| unidad_b - paragraphs | short+formal | 100 | 51.7 | 3.0 |
| unidad_b - paragraphs | short+informal | 100 | 51.3 | 1.5 |
| unidad_b - paragraphs | long+formal | 74 | 188.9 | 16.5 |
| unidad_b - paragraphs | long+informal | 60 | 141.3 | 11.7 |
| desacople_informal | short+informal | 100 | 46.7 | 4.2 |
| desacople_informal | long+informal | 22 | 222.3 | 27.2 |
| one_shot | short+formal | 100 | 40.0 | 0.1 |
| one_shot | short+informal | 0 | 28.8 | 0.4 |
| one_shot | long+formal | 92 | 153.3 | 10.7 |
| one_shot | long+informal | 84 | 158.5 | 20.9 |
| few_shot | short+formal | 100 | 40.8 | 2.5 |
| few_shot | short+informal | 94 | 32.0 | 1.5 |
| few_shot | long+formal | **100** | 170.4 | 8.9 |
| few_shot | long+informal | 99 | 163.2 | 5.4 |
| retry_concrete | short+formal | 100 | 35.2 | 2.1 |
| retry_concrete | short+informal | 100 | 41.8 | 4.3 |
| retry_concrete | long+formal | 94 | 180.5 | 20.2 |
| retry_concrete | long+informal | 89 | 181.5 | 19.2 |
| retry_generic | short+formal | 100 | 35.6 | 2.8 |
| retry_generic | short+informal | 100 | 39.0 | 4.8 |
| retry_generic | long+formal | 87 | 166.8 | 27.5 |
| retry_generic | long+informal | 66 | 162.0 | 29.7 |
| retry_mh | short+formal | 100 | 35.3 | 2.8 |
| retry_mh | short+informal | 100 | 47.5 | 2.2 |
| retry_mh | long+formal | 56 | 156.9 | 26.6 |
| retry_mh | long+informal | 87 | 179.3 | 23.7 |
| countdown | short+formal | 100 | 45.2 | 0.8 |
| countdown | short+informal | **100** | 45.3 | 0.7 |
| countdown | long+formal | **100** | 158.8 | 7.9 |
| countdown | long+informal | **100** | 170.2 | 0.5 |

**Las 3 diferencias más grandes frente al baseline (combinaciones):** las tres celdas que estaban en **0%** pasan a **100%**:

1. `long+informal` 0 → 100 (countdown, media 170.2, desvío 0.5).
2. `long+formal` 0 → 100 (countdown y few_shot).
3. `short+informal` 0 → 100 (countdown; también unidad_b, desacople_informal y retry_*).

---

## 7. Hallazgos

1. **Ganadora: `countdown` (CAPEL).** 100% en las 4 celdas, media pegada al objetivo (45.2 / 45.3 / 158.8 / 170.2) y desvío mínimo (0.5–7.9). Supera a todas las demás, incluidos los reintentos.
2. **El registro informal acorta sistemáticamente.** Con el prompt naive, informal cae a 21 (short) y 69 (long) palabras frente a 36 y 117 en formal; incluso el aislado informal da 31.4 vs 83.5 formal. El guardrail por sí solo no lo corrige.
3. **Longitud y formalidad sí se afectan entre sí** (a pesar del guardrail). `desacople_informal` revierte el efecto: long+informal pasa de 69 a 222 palabras (78% overshoot), confirmando que las señales de "brevedad" del módulo informal causaban la subproducción.
4. **`few_shot` es el mejor prompt simple.** 94–100% en las 4 celdas con desvíos bajos; `one_shot` falla en short+informal (0%).
5. **Los reintentos arreglan short pero no long.** retry_* logran 100% en short; en long quedan entre 56% (retry_mh formal) y 94%, con medias sesgadas (retry_concrete long ≈181). `retry_mh` no supera al retry concreto pese al juez.

---

## 8. Conclusión

- Técnica recomendada: **CAPEL/countdown** (100% en ventana, precisión casi perfecta).
- `few_shot` como alternativa ligera si se quiere texto normal, sin marcadores.
- Limitación: n=100 por celda, un solo modelo y un solo prompt; falta validar si el formato con marcadores de countdown generaliza a otros modelos y tareas.
