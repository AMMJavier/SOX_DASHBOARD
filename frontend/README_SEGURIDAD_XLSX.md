# HITSS / SOX Dashboard — corrección de vulnerabilidad `xlsx`

Fecha: 23 de octubre de 2026

## Motivo

`npm audit` reportó `xlsx@0.18.5` (SheetJS) por GHSA-4r6h-8v6p-xvw6 (Prototype Pollution) y GHSA-5pgg-2g8v-p4x9 (ReDoS). La versión publicada en el registro npm no ofrece una actualización que remedie ambas.

## Cambio aplicado

- Se elimina `xlsx` de `package.json` y se agrega `write-excel-file@^4.1.1` (MIT), diseñado para escribir XLSX desde navegador.
- Se elimina `file-saver`, ya que el nuevo paquete realiza la descarga directamente.
- Se reescribe `src/utils/exportExcel.js` y se preservan la pestaña SOX, las seis columnas, el nombre predeterminado del reporte y el filtro que excluye decisiones `Mantener`.
- Las celdas exportadas se marcan como texto para evitar que contenido recibido de servicios externos se convierta en fórmulas.
- Las pantallas de Campañas, Histórico y Auditoría capturan errores de exportación. En Histórico solo se registra la descarga Excel después de que la operación termina y ya no se registra además una descarga PDF.
- No se modifican los routers, autenticación, Assets ni backend.

## Instalación en el servidor HITSS

**Hacer respaldo antes de sobrescribir archivos.** En la carpeta `sox-dashboard`, extraer el ZIP, que contiene `frontend/...`.

```bash
cd /data/sisauto/Proyecto_Sox/sox-dashboard/frontend
npm install --include=optional
npm audit
npm run build
```

Si `xlsx` sigue instalado después de `npm install`, comprobar dependencias con `npm ls xlsx`. Si figura como dependencia directa de un manifiesto antiguo, comprobar que `package.json` se actualizó. Evitar `npm audit fix --force` sin evaluar sus cambios.

Al terminar, publicar `dist/` según la configuración Nginx del servidor y validar la descarga desde SOX > Control 7 > Campañas / Histórico / Auditoría.

## Validaciones y límites

- 78 archivos JS/JSX parseados correctamente.
- Prueba simulada del exportador: filtro de `Mantener`, seis columnas, celda de texto y nombre/hoja correctos.
- Revisión estática: no quedan imports de `xlsx` ni de `file-saver` en el código fuente.
- **No** se ejecutó `npm audit` ni `npm run build` con el paquete nuevo aquí porque no existe conectividad de red hacia npm para instalar la nueva dependencia.
- La eliminación de esta vulnerabilidad concreta no certifica que todas las dependencias del sistema estén libres de otras vulnerabilidades. Validar `npm audit` con el nuevo lockfile en HITSS.

Referencias:
- https://osv.dev/vulnerability/GHSA-4r6h-8v6p-xvw6
- https://osv.dev/vulnerability/GHSA-5pgg-2g8v-p4x9
- https://www.npmjs.com/package/write-excel-file
