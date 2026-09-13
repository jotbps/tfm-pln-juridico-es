# Contenido del Anexo II digital y correspondencia con el TFM

La organización conserva los archivos del estudio con nombres normalizados.
El código fuente y las dependencias se consultan en codigo/. El registro
verificacion/correspondencia_TFM_historica.json conserva la comprobación
realizada antes de retirar del Word los listados de código; identifica su
documento fuente por SHA-256. Esta normalización no vuelve a validar el Word.

| Apartado o tabla | Archivos | Funciones |
|---|---|---|
| 5.6 y tabla AII.1 | resultados/muestra_boe_metadatos.csv; resultados/distribucion_muestra.csv; resultados/exclusiones_extraccion.csv; resultados/manifiesto_reproducibilidad.json | Identificar las 400 disposiciones, fechas, secciones, enlaces, exclusiones y configuración. |
| 6.4 y Anexo II: script principal | codigo/tfm_boe_experiment.py; codigo/requirements.txt; datos/terminos_juridicos_125.csv | Procedimiento original y listado de las 125 expresiones. |
| Tabla 7.2 | resultados/tabla_longitudes_resumen.csv; resultados/longitudes_por_documento.csv | Mediana, P90, P95, umbrales y 400 mediciones de cada tokenizador. |
| Figura 7.1 | resultados/figura_ecdf_longitudes_sin_titulo.png; resultados/figura_ecdf_longitudes.png | Distribución acumulada de longitudes. Se conserva una versión sin título interior y la salida original del script. |
| Tabla 7.3 | resultados/tabla_fragmentacion_resumen.csv | Resumen de fragmentación de BETO, RoBERTalex, MEL y MrBERT-legal. |
| Tabla 7.4 | analisis_complementario/cobertura_ventanas.csv | Cobertura real por la ventana de entrada de cada modelo. |
| Tabla AII.2 | resultados/fragmentacion_por_categoria.csv | Fragmentación por categoría y tokenizador. |
| Tabla AII.3 | resultados/svm_metricas_por_clase.csv; resultados/svm_resumen.json | Precisión, recall, F1, soporte y métricas globales del baseline. |
| Tabla AII.4 | resultados/svm_matriz_confusion.csv; resultados/svm_matriz_confusion.png | Matriz del test temporal de 2025. Filas: clase real; columnas: predicción. |
| Tabla AII.5 | datos/terminos_juridicos_125.csv; resultados/fragmentacion_terminos_formato_ancho.csv; resultados/fragmentacion_terminos_detalle.csv | Listado de expresiones, recuentos y piezas exactas de tokenización de cada expresión. |
| Tabla AII.6 | analisis_complementario/sensibilidad_resumen.csv; analisis_complementario/sensibilidad_por_fecha.csv | Rangos de los percentiles y los 480 cálculos individuales por omisión de fecha. |
| Interpretación de 7.2 | analisis_complementario/comparativa_percentiles.csv; analisis_complementario/distribucion_por_fecha.csv; analisis_complementario/errores_seccion_III.json | Comparaciones con BETO, concentración de la cola, recuentos por fecha y lectura de los tres errores del SVM. |
| Anexo II: análisis complementario | codigo/analisis_complementario.py; analisis_complementario/manifiesto_analisis_complementario.json | Reproducción de los cálculos complementarios y huellas de sus entradas. |
| Trazabilidad | resultados/ejecucion.log; resultados/manifiesto_reproducibilidad.json | Registro original y configuración de la ejecución. |
| Verificación del paquete | codigo/verificar_anexo.py; verificacion/; INVENTARIO.csv; SHA256SUMS.txt | Comprobaciones aritméticas, coherencia con el Word e integridad de archivos. |

## Archivos que no sustituyen la versión final del TFM

`resultados/texto_para_integrar_en_TFM.md` es un borrador generado por el script original.
Se conserva para trazabilidad, no como redacción final. La figura de fragmentación
media y la imagen de la matriz de confusión son salidas auxiliares.

## Diferencias de precisión

Los CSV conservan más decimales que el Word. La comprobación del documento se
realiza con tolerancias acordes al redondeo impreso; esto no equivale a cambiar los datos.

## Límites

La sensibilidad por fecha es descriptiva y no un intervalo de confianza poblacional.
Las piezas tokenizadas son las de las 125 expresiones; para cada disposición se
conserva su longitud, no toda su secuencia de tokens.
Los tres errores de la sección III se conocen por la matriz agregada. Este paquete
no identifica qué tres disposiciones concretas se clasificaron incorrectamente.
