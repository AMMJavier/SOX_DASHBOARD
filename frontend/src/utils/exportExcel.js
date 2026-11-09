import ExcelJS from "exceljs/dist/exceljs.min.js";
import { saveAs } from "file-saver";

/** Exportación SOX compatible con ExcelJS (sin dependencia SheetJS vulnerable). */
export async function exportToExcel(data, fileName = "reporte-sox.xlsx") {
  const filteredData = (Array.isArray(data) ? data : []).filter(
    (item) => String(item.decision || "").toLowerCase() !== "mantener"
  );
  const workbook = new ExcelJS.Workbook();
  const worksheet = workbook.addWorksheet("SOX");
  worksheet.columns = [
    { header: "REQ", key: "req", width: 24 },
    { header: "Nombre VPN", key: "vpn", width: 42 },
    { header: "Gerente Asignado", key: "manager", width: 36 },
    { header: "Estado", key: "status", width: 20 },
    { header: "Decisión", key: "decision", width: 20 },
    { header: "Observación", key: "observation", width: 55 },
  ];
  // Mantener todos los valores como texto e impedir interpretación de fórmulas.
  const plain = (value) => {
    const text = String(value ?? "-");
    return /^[=+@\-\t\r\n]/.test(text) ? `'${text}` : text;
  };
  filteredData.forEach((item) => {
    worksheet.addRow({
      req: plain(item.req), vpn: plain(item.nombre_vpn), manager: plain(item.manager),
      status: plain(item.status), decision: plain(item.decision),
      observation: plain(item.observation),
    });
  });
  worksheet.getRow(1).font = { bold: true, color: { argb: "FFFFFFFF" } };
  worksheet.getRow(1).fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FF1D4ED8" } };
  worksheet.autoFilter = { from: "A1", to: "F1" };
  worksheet.views = [{ state: "frozen", ySplit: 1 }];
  const buffer = await workbook.xlsx.writeBuffer();
  saveAs(new Blob([buffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }), fileName);
}
