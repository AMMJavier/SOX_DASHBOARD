import { authenticatedFetch, API_BASE_URL } from "../apiFetch";
const BASE_URL = `${API_BASE_URL}/assets/upload`;

async function parseResponse(response) {
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = data.detail;

    if (typeof detail === "string") {
      throw new Error(detail);
    }

    if (detail?.errores?.length) {
      throw new Error(
        `${detail.mensaje || "Error de validación"}\n` +
          detail.errores
            .map((item) => `Fila ${item.fila}: ${item.error}`)
            .join("\n")
      );
    }

    throw new Error(detail?.mensaje || "Error al procesar la solicitud.");
  }

  return data;
}

export async function previewAssetsCsv(file, delimiter = "auto") {
  const formData = new FormData();

  formData.append("file", file);
  formData.append("delimiter", delimiter);

  const response = await authenticatedFetch(`${BASE_URL}/preview`, {
    method: "POST",
    body: formData,
  });

  return parseResponse(response);
}

export async function confirmAssetsUpload(items) {
  const response = await authenticatedFetch(`${BASE_URL}/confirm`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ items }),
  });

  return parseResponse(response);
}

export async function saveAssetsManual(items) {
  const response = await authenticatedFetch(`${BASE_URL}/manual`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ items }),
  });

  return parseResponse(response);
}