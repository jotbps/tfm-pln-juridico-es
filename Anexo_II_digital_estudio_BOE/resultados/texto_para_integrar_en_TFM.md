# Texto y tablas generados para integrar en el TFM

> Este fichero se genera automáticamente a partir de resultados reales. Revise la redacción y no copie nada si la ejecución no finalizó sin errores.

## Datos para 5.6 Descripción de la muestra

La muestra exploratoria quedó formada por **400 disposiciones BOE-A**, publicadas en **40 fechas** de los años **2021–2025** y distribuidas entre **5 códigos de sección**. La selección partió de fechas ancla predefinidas y, dentro de cada sumario, aplicó un muestreo reproducible con rotación entre secciones. De cada disposición se recuperó el cuerpo textual mediante la URL XML publicada en el sumario; cuando el XML no produjo texto válido, se utilizó la versión HTML. Se excluyeron del texto analizado el título y los metadatos estructurados utilizados para construir la muestra.

La muestra no constituye un corpus de jurisprudencia ni permite estimar directamente la longitud de las resoluciones CENDOJ. Las disposiciones del BOE suelen presentar estructura y extensión diferentes de las resoluciones judiciales; por ello, las longitudes observadas se interpretan como una **cota inferior exploratoria** del problema de contexto que previsiblemente planteará la jurisprudencia.

## Datos para 6.4 Procedimiento del estudio exploratorio

Se emplearon únicamente los tokenizadores, sin descargar ni ejecutar los pesos de los modelos. Para cada documento se calculó la longitud de la secuencia incluyendo los tokens especiales y sin truncamiento. Se registraron mediana, percentiles 90 y 95 y proporción de documentos que supera 512, 4.096 y 8.192 tokens. Los tokenizadores y revisiones resueltas fueron: BETO: dccuchile/bert-base-spanish-wwm-cased (c4d86612f51b4f46759c8390d1798c2febe71b93); RoBERTalex: PlanTL-GOB-ES/RoBERTalex (52ba14c94da3d66d1dcb8ae9efb4c2a1dee5fcc2); MEL: IIC/MEL (4584d5998b31adaeb9faebf2d960354971a513b5); MrBERT-legal: BSC-LT/MrBERT-legal (7e86e69d580ac37e4b505580a8950dd003f4a457).

La fragmentación léxica se midió sobre **125 expresiones predefinidas**, agrupadas en latinismos, colocaciones jurídicas, fórmulas rituales y términos técnicos o arcaizantes. Para evitar que las expresiones multi-palabra quedaran penalizadas por su mera longitud, el indicador principal fue el número de subtokens por palabra ortográfica; se añadió la proporción de expresiones cuyo número de subtokens supera el de palabras. No se añadieron tokens especiales en este análisis.

El baseline TF-IDF con LinearSVC, entrenado con los años 2021, 2022, 2023, 2024 y evaluado temporalmente en 2025, obtuvo una F1-macro de 0,958 sobre 4 clases (n_train=316; n_test=78). El detalle por clase y la matriz de confusión se incluyen en el Anexo II.

## Tabla 7.2. Distribución de longitudes tokenizadas

| Tokenizador | Mediana | P90 | P95 | % >512 | % >4.096 | % >8.192 |
|---|---|---|---|---|---|---|
| BETO | 819,0 | 9800,4 | 18110,9 | 65,5 | 22,8 | 10,8 |
| RoBERTalex | 759,5 | 8905,9 | 16621,8 | 63,2 | 21,0 | 10,5 |
| MEL | 882,0 | 10228,8 | 19808,7 | 67,2 | 23,8 | 11,5 |
| MrBERT-legal | 899,0 | 11013,8 | 19358,9 | 68,8 | 24,0 | 11,5 |

**Nota.** Longitudes calculadas sobre el cuerpo depurado del documento, incluyendo tokens especiales y sin truncamiento. La muestra BOE no equivale a jurisprudencia; los resultados son una cota inferior exploratoria para el caso CENDOJ.

## Tabla 7.3. Fragmentación del léxico jurídico

| Tokenizador | Subtokens/palabra (media) | Subtokens/palabra (mediana) | % términos fragmentados | Exceso medio de subtokens |
|---|---|---|---|---|
| BETO | 1,33 | 1,00 | 46,40 | 0,78 |
| RoBERTalex | 1,17 | 1,00 | 20,80 | 0,38 |
| MEL | 1,51 | 1,33 | 71,20 | 1,20 |
| MrBERT-legal | 1,35 | 1,25 | 54,40 | 0,82 |

**Nota.** Se considera fragmentada una expresión cuando el número de subtokens supera el número de palabras ortográficas. El listado completo y las piezas producidas por cada tokenizador se incluyen en el Anexo II.

## Interpretación sugerida para 7.2

Los resultados convierten en observación medida dos hipótesis que en la revisión se formulaban únicamente a partir de las propiedades declaradas de los modelos. En primer lugar, la distribución de longitudes permite cuantificar qué proporción de disposiciones puede procesarse íntegramente con ventanas de 512, 4.096 y 8.192 tokens. En segundo lugar, la fragmentación demuestra que el tamaño nominal del vocabulario no basta para inferir su adecuación al dominio: la comparación debe realizarse sobre unidades jurídicas concretas y mediante un indicador normalizado por número de palabras.

La interpretación debe mantenerse acotada al BOE. Un resultado favorable a 512 tokens en esta muestra no demostraría que esa ventana sea suficiente para resoluciones judiciales; del mismo modo, una menor fragmentación léxica no acredita por sí sola mejor clasificación. Ambas mediciones sirven para priorizar candidatos y estrategias de segmentación, pero la decisión final sobre CENDOJ requiere el experimento específico previsto para la segunda fase.
