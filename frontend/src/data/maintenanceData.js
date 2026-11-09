export const maintenanceSummary = {
  total: 156,
  completed: 120,
  pending: 28,
  critical: 8,
};


export const maintenanceOrders = [
  {
    id: "MT-001",
    asset: "Router Cisco ISR 4331",
    type: "Preventivo",
    technician: "Carlos Ramírez",
    location: "Data Center Quito",
    date: "2026-07-25",
    status: "Completado",
  },
  {
    id: "MT-002",
    asset: "Switch Cisco Catalyst 9300",
    type: "Correctivo",
    technician: "Juan Pérez",
    location: "Planta Guayaquil",
    date: "2026-07-28",
    status: "Pendiente",
  },
  {
    id: "MT-003",
    asset: "UPS APC 1500VA",
    type: "Preventivo",
    technician: "María González",
    location: "Sucursal Quito",
    date: "2026-07-30",
    status: "Programado",
  },
  {
    id: "MT-004",
    asset: "Firewall Fortigate 100F",
    type: "Correctivo",
    technician: "Carlos Ramírez",
    location: "Data Center",
    date: "2026-07-31",
    status: "Crítico",
  },
];