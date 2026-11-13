export function registerExport({ type, module, description, records }) {
  const saved = JSON.parse(localStorage.getItem("exportsHistory")) || [];
  const user = JSON.parse(localStorage.getItem("soxUser"));

  const newExport = {
    id: Date.now(),
    type,
    module,
    description,
    records,
    user: user?.username || user?.name || "Usuario",
    date: new Date().toLocaleString(),
  };

  const updated = [newExport, ...saved];
  localStorage.setItem("exportsHistory", JSON.stringify(updated));
}