import ExcelJS from "exceljs/dist/exceljs.min.js";
import { saveAs } from "file-saver";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";

function printable(value) {
  const text = value === null || value === undefined ? "" : String(value).trim();
  return ["", "-", "–", "—"].includes(text) ? "Sin valor" : text;
}

function safeExcel(value) {
  const text = printable(value);
  // No permitir que datos externos se interpreten como fórmulas al abrir Excel.
  return /^[=+\-@\t\r\n]/.test(text) ? `'${text}` : text;
}

function formatDate(value) {
  if (!value) return "";
  const [day, time = ""] = String(value).split("T");
  const [year, month, date] = day.split("-");
  if (!year || !month || !date) return String(value);
  return `${date}/${month}/${year} ${time.split(".")[0]}`.trim();
}

function reportRows(logs, isExcel = false) {
  const value = isExcel ? safeExcel : printable;
  return logs.map((log) => ({
    "Fecha modificación": formatDate(log.fecha_cambio),
    "ID activo": log.dispositivo_id ?? "",
    "Dispositivo": value(log.dispositivo || `Activo #${log.dispositivo_id}`),
    "Serial": value(log.serial),
    "Campo modificado": value(log.campo_modificado),
    "Estado anterior": value(log.valor_anterior),
    "Estado nuevo": value(log.valor_nuevo),
    "Usuario": value(log.usuario),
    "Origen": value(log.origen),
    "Operación": value(log.operacion),
  }));
}

export async function exportAssetHistoryExcel(logs, filename = "Assets_Historial_Completo.xlsx") {
  const records = reportRows(logs, true);
  const headers = [
    "Fecha modificación", "ID activo", "Dispositivo", "Serial",
    "Campo modificado", "Estado anterior", "Estado nuevo",
    "Usuario", "Origen", "Operación",
  ];
  const widths = [22, 12, 37, 22, 22, 38, 38, 18, 18, 14];
  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet("Historial de activos", {
    views: [{ state: "frozen", ySplit: 1 }],
  });
  sheet.columns = headers.map((header, i) => ({ header, key: String(i), width: widths[i] }));

  for (const record of records) {
    const values = headers.map((header) => record[header]);
    // Valor tipado como texto: evita fórmulas inyectadas desde campos editables.
    sheet.addRow(values.map((value) => typeof value === "number" ? value : String(value ?? "")));
  }

  const heading = sheet.getRow(1);
  heading.font = { bold: true, color: { argb: "FFFFFFFF" } };
  heading.fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FF6D28D9" } };
  heading.alignment = { vertical: "middle", wrapText: true };
  heading.height = 24;
  sheet.autoFilter = { from: "A1", to: "J1" };

  const buffer = await workbook.xlsx.writeBuffer();
  saveAs(new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  }), filename);
}

export function exportAssetHistoryPdf(logs, filename = "Assets_Historial_Completo.pdf") {
  const rows = reportRows(logs);
  const doc = new jsPDF({ orientation: "landscape", unit: "mm", format: "a3" });
  doc.setFontSize(15);
  doc.text("HITSS / Assets - Historial de modificaciones", 12, 14);
  doc.setFontSize(9);
  doc.text(`Cambios exportados: ${rows.length} | Generado: ${new Date().toLocaleString("es-EC")}`, 12, 21);
  autoTable(doc, {
    startY: 27,
    head: [["Fecha", "ID", "Dispositivo", "Serial", "Campo", "Anterior", "Nuevo", "Usuario", "Origen"]],
    body: rows.map((r) => [
      r["Fecha modificación"], r["ID activo"], r["Dispositivo"], r["Serial"],
      r["Campo modificado"], r["Estado anterior"], r["Estado nuevo"],
      r["Usuario"], r["Origen"],
    ]),
    theme: "striped",
    styles: { fontSize: 7, overflow: "linebreak", cellPadding: 2.2 },
    headStyles: { fillColor: [88, 28, 135] },
    margin: { top: 27, left: 12, right: 12, bottom: 15 },
    columnStyles: {
      0: { cellWidth: 27 }, 1: { cellWidth: 12 }, 2: { cellWidth: 54 },
      3: { cellWidth: 28 }, 4: { cellWidth: 26 }, 5: { cellWidth: 55 },
      6: { cellWidth: 55 }, 7: { cellWidth: 29 }, 8: { cellWidth: 29 },
    },
    didDrawPage: (data) => {
      doc.setFontSize(8);
      doc.text(`Página ${data.pageNumber}`, doc.internal.pageSize.getWidth() - 31,
        doc.internal.pageSize.getHeight() - 8);
    },
  });
  doc.save(filename);
}
