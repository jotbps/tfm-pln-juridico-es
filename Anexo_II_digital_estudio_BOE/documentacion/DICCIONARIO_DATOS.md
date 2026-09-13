# Diccionario de datos

CSV: separador coma, punto decimal y texto UTF-8. Fechas como AAAAMMDD.
Los nombres se conservan tal como salen de los programas originales.

## analisis_complementario/cobertura_ventanas.csv

Filas de datos: 4.

- `model`: Nombre del modelo cuyo límite de entrada se evalúa.
- `window`: Ventana documentada, en tokens; tomada de la tabla 7.1 del TFM.
- `n`: Número de documentos.
- `n_fits`: Documentos con longitud menor o igual que la ventana.
- `pct_fits`: Porcentaje de documentos que caben completos.
- `n_exceeds`: Documentos que superan la ventana.
- `pct_exceeds`: Porcentaje de documentos que superan la ventana.

## analisis_complementario/comparativa_percentiles.csv

Filas de datos: 4.

- `tokenizer`: Nombre del tokenizador evaluado.
- `n`: Número de documentos.
- `mediana`: Mediana de longitud en tokens.
- `mediana_pct_vs_BETO`: 100 * (estadístico del tokenizador / estadístico de BETO - 1).
- `P90`: Percentil 90, interpolación lineal.
- `P90_pct_vs_BETO`: 100 * (estadístico del tokenizador / estadístico de BETO - 1).
- `P95`: Percentil 95, interpolación lineal.
- `P95_pct_vs_BETO`: 100 * (estadístico del tokenizador / estadístico de BETO - 1).
- `P90_over_median`: P90 dividido entre mediana.
- `P95_over_median`: P95 dividido entre mediana.
- `top_5pct_n`: Número de documentos usados para describir el 5 % superior (20).
- `top_5pct_token_share`: Porcentaje de tokens totales concentrados en los veinte textos más largos de ese tokenizador.

## analisis_complementario/distribucion_por_fecha.csv

Filas de datos: 40.

- `issue_date`: Fecha del sumario, formato AAAAMMDD; conservar como texto.
- `n_documents`: Número de documentos de esa fecha.

## analisis_complementario/sensibilidad_por_fecha.csv

Filas de datos: 480.

- `tokenizer`: Nombre del tokenizador evaluado.
- `omitted_issue_date`: Fecha omitida en la comprobación de sensibilidad.
- `n_omitted`: Documentos retirados en esa omisión.
- `n_remaining`: Documentos conservados tras la omisión.
- `metric`: Estadístico analizado: mediana, P90 o P95.
- `full_sample`: Valor del estadístico sobre los 400 documentos.
- `omission_value`: Valor recalculado tras retirar una fecha.
- `pct_change`: 100 * (omission_value / full_sample - 1).

## analisis_complementario/sensibilidad_resumen.csv

Filas de datos: 12.

- `tokenizer`: Nombre del tokenizador evaluado.
- `metric`: Estadístico analizado: mediana, P90 o P95.
- `full_sample`: Valor del estadístico sobre los 400 documentos.
- `minimum`: Menor valor entre las 40 omisiones.
- `maximum`: Mayor valor entre las 40 omisiones.
- `maximum_abs_pct_change`: Mayor valor absoluto de la variación porcentual en las 40 omisiones.

## datos/terminos_juridicos_125.csv

Filas de datos: 125.

- `categoria`: Grupo léxico definido en el listado de expresiones.
- `termino`: Expresión jurídica evaluada.

## resultados/distribucion_muestra.csv

Filas de datos: 163.

- `year`: Año de publicación.
- `issue_date`: Fecha del sumario, formato AAAAMMDD; conservar como texto.
- `section_code`: Código de sección; T identifica Tribunal Constitucional en estas salidas.
- `section_name`: Nombre de la sección procedente de los metadatos.
- `n`: Número de documentos.

## resultados/exclusiones_extraccion.csv

Filas de datos: 1.

- `identifier`: Identificador oficial de la disposición BOE.
- `reason`: Motivo de exclusión registrado en la extracción.

## resultados/fragmentacion_por_categoria.csv

Filas de datos: 16.

- `tokenizer`: Nombre del tokenizador evaluado.
- `categoria`: Grupo léxico definido en el listado de expresiones.
- `n_terms`: Número de expresiones.
- `mean_subtokens_per_word`: Media de los cocientes individuales subtokens/palabra; no cociente de totales.
- `median_subtokens_per_word`: Mediana de los cocientes subtokens/palabra.
- `pct_fragmented`: Porcentaje de expresiones fragmentadas.

## resultados/fragmentacion_terminos_detalle.csv

Filas de datos: 500.

- `categoria`: Grupo léxico definido en el listado de expresiones.
- `termino`: Expresión jurídica evaluada.
- `tokenizer`: Nombre del tokenizador evaluado.
- `orthographic_words`: Palabras ortográficas en la expresión, contadas por WORD_RE.
- `subtokens`: Número de subtokens de la expresión sin tokens especiales.
- `excess_subtokens`: Subtokens menos palabras ortográficas.
- `subtokens_per_word`: Cociente entre subtokens y palabras ortográficas.
- `fragmented`: Verdadero si subtokens supera palabras ortográficas.
- `token_pieces`: Piezas producidas por el tokenizador, separadas por " | ".

## resultados/fragmentacion_terminos_formato_ancho.csv

Filas de datos: 125.

- `categoria`: Grupo léxico definido en el listado de expresiones.
- `termino`: Expresión jurídica evaluada.
- `orthographic_words`: Palabras ortográficas en la expresión, contadas por WORD_RE.
- `subtokens_BETO`: Subtokens de la expresión con BETO.
- `pieces_BETO`: Piezas de la expresión con BETO.
- `subtokens_RoBERTalex`: Subtokens de la expresión con RoBERTalex.
- `pieces_RoBERTalex`: Piezas de la expresión con RoBERTalex.
- `subtokens_MEL`: Subtokens de la expresión con MEL.
- `pieces_MEL`: Piezas de la expresión con MEL.
- `subtokens_MrBERT-legal`: Subtokens de la expresión con MrBERT-legal.
- `pieces_MrBERT-legal`: Piezas de la expresión con MrBERT-legal.

## resultados/longitudes_por_documento.csv

Filas de datos: 400.

- `identifier`: Identificador oficial de la disposición BOE.
- `issue_date`: Fecha del sumario, formato AAAAMMDD; conservar como texto.
- `year`: Año de publicación.
- `section_code`: Código de sección; T identifica Tribunal Constitucional en estas salidas.
- `section_name`: Nombre de la sección procedente de los metadatos.
- `department_name`: Denominación del departamento emisor.
- `char_count`: Número de caracteres del cuerpo depurado.
- `word_count`: Número de palabras según la expresión regular WORD_RE del script.
- `tokens_BETO`: Longitud del cuerpo con BETO, incluyendo tokens especiales y sin truncamiento.
- `tokens_RoBERTalex`: Longitud del cuerpo con RoBERTalex, incluyendo tokens especiales y sin truncamiento.
- `tokens_MEL`: Longitud del cuerpo con MEL, incluyendo tokens especiales y sin truncamiento.
- `tokens_MrBERT-legal`: Longitud del cuerpo con MrBERT-legal, incluyendo tokens especiales y sin truncamiento.

## resultados/muestra_boe_metadatos.csv

Filas de datos: 400.

- `issue_date`: Fecha del sumario, formato AAAAMMDD; conservar como texto.
- `year`: Año de publicación.
- `diary_number`: Número del boletín.
- `section_code`: Código de sección; T identifica Tribunal Constitucional en estas salidas.
- `section_name`: Nombre de la sección procedente de los metadatos.
- `department_code`: Código de departamento emisor.
- `department_name`: Denominación del departamento emisor.
- `epigraph`: Epígrafe del sumario; puede estar vacío.
- `identifier`: Identificador oficial de la disposición BOE.
- `title`: Título de la disposición, conservado como metadato y no usado como entrada.
- `url_xml`: Enlace de procedencia en formato XML.
- `url_html`: Enlace de procedencia en formato HTML.
- `url_pdf`: Enlace de procedencia en formato PDF.
- `source_format`: Formato del que se extrajo el cuerpo.
- `sha256_text`: Huella SHA-256 original del cuerpo depurado; el texto completo no está incluido.
- `char_count`: Número de caracteres del cuerpo depurado.
- `word_count`: Número de palabras según la expresión regular WORD_RE del script.

## resultados/svm_matriz_confusion.csv

Filas de datos: 4.

- `Unnamed: 0`: Índice exportado de la matriz: clase real.
- `1`: Recuento de predicciones en esta clase; la fila indica la clase real.
- `2A`: Recuento de predicciones en esta clase; la fila indica la clase real.
- `2B`: Recuento de predicciones en esta clase; la fila indica la clase real.
- `3`: Recuento de predicciones en esta clase; la fila indica la clase real.

## resultados/svm_metricas_por_clase.csv

Filas de datos: 4.

- `class_code`: Código de la clase.
- `class_name`: Nombre de la clase.
- `precision`: Verdaderos positivos entre predicciones de la clase.
- `recall`: Verdaderos positivos entre documentos reales de la clase.
- `f1`: Media armónica de precision y recall.
- `support`: Documentos reales de la clase en el test.

## resultados/tabla_fragmentacion_resumen.csv

Filas de datos: 4.

- `tokenizer`: Nombre del tokenizador evaluado.
- `n_terms`: Número de expresiones.
- `mean_subtokens`: Media de subtokens por expresión.
- `median_subtokens`: Mediana de subtokens por expresión.
- `p90_subtokens`: P90 de subtokens por expresión.
- `mean_subtokens_per_word`: Media de los cocientes individuales subtokens/palabra; no cociente de totales.
- `median_subtokens_per_word`: Mediana de los cocientes subtokens/palabra.
- `pct_fragmented`: Porcentaje de expresiones fragmentadas.
- `mean_excess_subtokens`: Media de subtokens menos palabras ortográficas.

## resultados/tabla_longitudes_resumen.csv

Filas de datos: 4.

- `tokenizer`: Nombre del tokenizador evaluado.
- `n`: Número de documentos.
- `median`: Mediana de longitud en tokens.
- `p90`: Percentil 90, interpolación lineal.
- `p95`: Percentil 95, interpolación lineal.
- `min`: Longitud mínima.
- `max`: Longitud máxima.
- `pct_gt_512`: Porcentaje que supera estrictamente 512 tokens.
- `pct_gt_4096`: Porcentaje que supera estrictamente 4096 tokens.
- `pct_gt_8192`: Porcentaje que supera estrictamente 8192 tokens.

