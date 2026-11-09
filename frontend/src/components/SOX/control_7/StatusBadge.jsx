export default function StatusBadge({ status }) {
  const styles = {
    Pendiente: "bg-amber-100 text-amber-700",
    Confirmado: "bg-green-100 text-green-700",
    Vencido: "bg-red-100 text-red-700",
    "Sin Responsable": "bg-violet-100 text-violet-700",
  };

  return (
    <span className={`rounded-lg px-4 py-2 text-xs font-bold ${styles[status]}`}>
      {status}
    </span>
  );
}