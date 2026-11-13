import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";

/**
 * Exporta a PDF exactamente las filas recibidas (las que se ven en pantalla, con sus filtros)
 * usando las columnas de esa pantalla (ver exportColumns.js). Horizontal: caben más columnas.
 */
export function exportToPdf(data, fileName = "reporte-sox.pdf", columns, title = "Reporte SOX") {
  const rows = Array.isArray(data) ? data : [];
  if (!Array.isArray(columns) || !columns.length) throw new Error("exportToPdf requiere las columnas de la pantalla");
  const doc = new jsPDF({ orientation: "landscape" });
  doc.setFontSize(13);
  doc.text(title, 14, 14);
  doc.setFontSize(9);
  doc.text(`Registros: ${rows.length} · Generado: ${new Date().toLocaleString()}`, 14, 20);
  autoTable(doc, {
    startY: 25,
    head: [columns.map((c) => c.header)],
    body: rows.map((item) => columns.map((c) => String(c.value(item) ?? "-"))),
    styles: { fontSize: 7, cellPadding: 1.5, overflow: "linebreak" },
    headStyles: { fillColor: [29, 78, 216] },
  });
  doc.save(fileName);
  return rows.length;
}
