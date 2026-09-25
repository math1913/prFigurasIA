# Cambios de prueba (revertir al terminar)

Valores de configuración cambiados el 25/09/2026 solo para probar en el PC de desarrollo con dos lectores ACR122U y dos tarjetas de prueba. El overlay NFC (`/overlay`, `nfc.overlay_channels`) es funcionalidad y se queda. Solo hay que revertir lo siguiente.

## Valores a revertir

| Archivo | Valor de prueba | Valor original |
| --- | --- | --- |
| `aliases.json` | `"04FA4E2ABF2A81": "Superman"` | No existía: borrar la línea |
| `aliases.json` | `"044C4A2ABF2A81": "Prince"` | No existía: borrar la línea |

Las dos líneas están juntas al principio de `aliases.json`. Se subieron a la rama `integracion-figuras-nfc-html` junto con este archivo, en un commit aparte titulado «Configuración de prueba NFC (revertir tras las pruebas)». Para deshacerlo todo de una vez, localiza el commit con `git log --oneline --grep "Configuración de prueba"` y ejecuta `git revert <hash>`: borra las dos líneas y este archivo.

## Lectores de este PC

| Lector (nombre PC/SC) | UID de la tarjeta de prueba | Logo asignado |
| --- | --- | --- |
| `ACS ACR122U PICC Interface 0` | `04FA4E2ABF2A81` | Superman |
| `ACS ACR122U PICC Interface 1` | `044C4A2ABF2A81` | Prince |

Los lectores NFC no tienen puerto que configurar. La aplicación usa todos los lectores PC/SC conectados y muestra sus nombres en el panel de control, así que no hay que revertir nada para ellos.
