# Informe de verificación del Anexo II digital

## Verificación actual del paquete

Resultado: PASS. Se completaron 60 comprobaciones de coherencia aritmética,
sintaxis y recálculo de los resultados complementarios, sin descargas,
sin tokenización y sin entrenamiento. El detalle y las versiones del entorno
figuran en resultado_verificacion.json.

Se conservan los 400 documentos identificados, sus 40 fechas, las 125 expresiones
y los resultados originales. No se han cambiado los datos, las imágenes, el
registro de ejecución ni los scripts principal y complementario. Se han actualizado
nombres y referencias editoriales, la ruta del verificador, el inventario y los
hashes. SHA256SUMS.txt contiene una huella por archivo excepto la de sí mismo.
El verificador comprueba esas huellas después de las comprobaciones aritméticas.

## Registro histórico del contraste con el TFM

correspondencia_TFM_historica.json conserva las 63 comprobaciones registradas
anteriormente, con el documento fuente identificado por su SHA-256. Es un
registro histórico y no una comprobación nueva del Word. Las rutas mencionadas
se han normalizado para que permitan localizar los archivos actuales. Las
antiguas comprobaciones de código impreso corresponden al documento fuente
histórico, no a la memoria posterior sin listados.

## Alcance y límites

No se ha repetido la descarga del BOE, la tokenización ni el entrenamiento
TF-IDF/SVM. La comprobación aritmética usa los resultados archivados.
Los cuerpos completos, las predicciones individuales y el clasificador ajustado
no figuran en el paquete. No se han reconstruido esos archivos ausentes.
Los hashes de cuerpos no pueden recalcularse sin esos textos.

Las dependencias del programa principal usan rangos de versiones. La descarga
original registra revisiones de los tokenizadores, pero no fija el argumento
revision. La comprobación de este paquete no es una repetición integral del
experimento ni una validación de su generalización.

## Integridad

INVENTARIO.csv y SHA256SUMS.txt se han regenerado con los nombres y contenidos
actuales. Se conserva el paquete anterior por separado; este archivo corresponde
únicamente al material de entrega con nombres normalizados.
