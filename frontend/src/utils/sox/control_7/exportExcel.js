import ExcelJS from "exceljs/dist/exceljs.min.js";
import { saveAs } from "file-saver";

/**
 * Exporta a Excel exactamente las filas recibidas (las que se ven en pantalla, con sus filtros)
 * usando las columnas de esa pantalla (ver exportColumns.js). Sin dependencia SheetJS vulnerable.
 */
export async function exportToExcel(data, fileName = "reporte-sox.xlsx", columns, sheetName = "SOX") {
  const rows = Array.isArray(data) ? data : [];
  if (!Array.isArray(columns) || !columns.length) throw new Error("exportToExcel requiere las columnas de la pantalla");
  const workbook = new ExcelJS.Workbook();
  const worksheet = workbook.addWorksheet(sheetName.slice(0, 31));
  worksheet.columns = columns.map((c, index) => ({ header: c.header, key: `c${index}`, width: c.width || 20 }));
  // Todo como texto e impedir que Excel interprete fórmulas (=, +, @, -).
  const plain = (value) => {
    const s = String(value ?? "-");
    return /^[=+@\-\t\r\n]/.test(s) && s !== "-" ? `'${s}` : s;
  };
  rows.forEach((item) => {
    worksheet.addRow(Object.fromEntries(columns.map((c, index) => [`c${index}`, plain(c.value(item))])));
  });
  worksheet.getRow(1).font = { bold: true, color: { argb: "FFFFFFFF" } };
  worksheet.getRow(1).fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FF1D4ED8" } };
  worksheet.autoFilter = { from: { row: 1, column: 1 }, to: { row: 1, column: columns.length } };
  worksheet.views = [{ state: "frozen", ySplit: 1 }];
  const buffer = await workbook.xlsx.writeBuffer();
  saveAs(new Blob([buffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }), fileName);
  return rows.length;
}
