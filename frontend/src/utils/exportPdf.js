import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";

export function exportToPdf(
  data,
  fileName = "reporte-sox.pdf"
) {

  // Excluir VPN con decisión Mantener
  const filteredData = data.filter(
    (item) =>
      item.decision?.toLowerCase() !== "mantener"
  );

  const doc = new jsPDF();
  doc.text(
    "Reporte de Validaciones SOX",
    14,
    15
  );

  autoTable(doc, {
    startY: 25,
    head: [[
      "REQ",
      "Nombre VPN",
      "Gerente",
      "Estado",
      "Decisión",
      "Observación"
      
    ]],


    body: filteredData.map(
      (item) => [
        item.req || "-",
        item.nombre_vpn || "-",
        item.manager || "-",
        item.status || "-",
        item.decision || "-",
        item.observation || "-",
       
      ]
    ),
  });

  doc.save(fileName);

}