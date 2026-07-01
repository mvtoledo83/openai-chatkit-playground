import { CARDS_API_URL, CARDS_TOKEN_URL } from "./config";

export type CardRegistrationInput = {
  label: string;
  cardNumber: string;
  brand: string;
  cardholderName: string;
  customerId: string;
  expiryMonth: number;
  expiryYear: number;
  cvv: string;
};

export type CardRegistrationResult = {
  cardId: string;
  label: string;
  brand: string;
  cardholderName: string;
  customerId: string;
  endpoint: string;
  last4: string;
};

export type SavedCardSummary = {
  id: string;
  label: string;
  brand: string;
  cardholderName: string;
  last4: string;
};

type CreateCardApiResponse = {
  card_id?: string;
};

type WalletApiError = {
  detail?: string | { message?: string };
  message?: string;
};

type WalletListItem = {
  card_id?: string;
  card_name?: string;
  label?: string;
  brand?: string;
  cardholder_name?: string;
  customer_id?: string;
  status?: string;
  bin?: string;
  expiration_month?: number;
  expiration_year?: number;
  cardholder?: {
    name?: string;
  };
  last_four_digits?: string;
  last4?: string;
  last_digits?: string;
};

const wait = (timeMs: number) =>
  new Promise<void>((resolve) => {
    setTimeout(resolve, timeMs);
  });

const shouldUseRealApi =
  String(import.meta.env.VITE_ENABLE_CARDS_API ?? "false").toLowerCase() ===
  "true";

type AccessTokenApiResponse = {
  access_token?: string;
};

export async function getAccessToken(): Promise<string> {
  const response = await fetch(CARDS_TOKEN_URL, {
    method: "GET",
    headers: {
      accept: "application/json",
    },
  });

  if (!response.ok) {
    const errorPayloadText = await response.text();
    throw new Error(mapWalletError(response.status, errorPayloadText));
  }

  const data = (await response.json()) as AccessTokenApiResponse;
  if (!data.access_token) {
    throw new Error("Resposta de token sem access_token.");
  }

  return data.access_token;
}

export async function registerCard(
  payload: CardRegistrationInput,
): Promise<CardRegistrationResult> {
  if (shouldUseRealApi) {
    const accessToken = await getAccessToken();
    const body = {
      card_number: payload.cardNumber,
      brand: payload.brand,
      cardholder_name: payload.cardholderName,
      customer_id: payload.customerId,
      expiration_month: String(payload.expiryMonth).padStart(2, "0"),
      expiration_year: String(payload.expiryYear).slice(-2),
      security_code: payload.cvv,
    };

    const response = await fetch(CARDS_API_URL, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorPayloadText = await response.text();
      throw new Error(mapWalletError(response.status, errorPayloadText));
    }

    const data = (await response.json()) as CreateCardApiResponse;
    return {
      cardId: data.card_id ?? `card_${Date.now()}`,
      label: payload.label,
      brand: payload.brand,
      cardholderName: payload.cardholderName,
      customerId: payload.customerId,
      endpoint: CARDS_API_URL,
      last4: payload.cardNumber.slice(-4),
    };
  }

  await wait(650);

  if (payload.cardNumber.endsWith("0000")) {
    throw new Error("Cartao recusado no modo sandbox fake.");
  }

  return {
    cardId: `card_${Date.now()}`,
    label: payload.label,
    brand: payload.brand,
    cardholderName: payload.cardholderName,
    customerId: payload.customerId,
    endpoint: CARDS_API_URL,
    last4: payload.cardNumber.slice(-4),
  };
}

export async function getSavedCards(
  customerId: string,
): Promise<SavedCardSummary[]> {
  if (!shouldUseRealApi) {
    return [];
  }

  const accessToken = await getAccessToken();
  const listUrl = `${CARDS_API_URL}?customer_id=${encodeURIComponent(customerId)}`;
  const response = await fetch(listUrl, {
    method: "GET",
    headers: {
      authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    const errorPayloadText = await response.text();
    throw new Error(mapWalletError(response.status, errorPayloadText));
  }

  const payload: unknown = await response.json();
  const rows = extractWalletRows(payload);

  return rows.map((row, index) => {
    const rawId = row.card_id ?? `card_row_${index}`;
    const rawLast4 = row.last_four_digits ?? row.last4 ?? row.last_digits ?? "----";
    const normalizedLast4 = String(rawLast4).slice(-4);
    const rawLabel =
      row.card_name ?? row.label ?? `${row.brand ?? "cartao"} final ${normalizedLast4}`;
    const rawBrand = row.brand ?? "Bandeira nao informada";
    const rawCardholder = row.cardholder_name ?? row.cardholder?.name ?? "Titular nao informado";

    return {
      id: rawId,
      label: rawLabel,
      brand: rawBrand,
      cardholderName: rawCardholder,
      last4: normalizedLast4,
    };
  });
}

export async function deleteCard(cardId: string): Promise<void> {
  if (!shouldUseRealApi) {
    return;
  }

  const accessToken = await getAccessToken();
  const response = await fetch(`${CARDS_API_URL}/${cardId}`, {
    method: "DELETE",
    headers: {
      authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    const errorPayloadText = await response.text();
    throw new Error(mapWalletError(response.status, errorPayloadText));
  }
}

function extractWalletRows(payload: unknown): WalletListItem[] {
  if (Array.isArray(payload)) {
    return payload.filter(isWalletListItem);
  }

  if (!isRecord(payload)) {
    return [];
  }

  const cards = payload.cards;
  if (Array.isArray(cards)) {
    return cards.filter(isWalletListItem);
  }

  const items = payload.items;
  if (Array.isArray(items)) {
    return items.filter(isWalletListItem);
  }

  return [];
}

function isWalletListItem(value: unknown): value is WalletListItem {
  return isRecord(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function mapWalletError(status: number, rawPayload: string): string {
  const genericMessage = "Nao foi possivel salvar o cartao no momento.";
  const parsed = parseWalletError(rawPayload);
  const apiMessage =
    parsed?.message ??
    (typeof parsed?.detail === "string" ? parsed.detail : undefined) ??
    (typeof parsed?.detail === "object" ? parsed.detail?.message : undefined);

  if (status === 401 || status === 403) {
    return "Acesso negado pela API de wallet. Verifique as credenciais GETNET_CLIENT_ID_API/GETNET_CLIENT_SECRET_API no backend.";
  }

  if (status === 400 || status === 422) {
    return apiMessage ?? "Dados do cartao invalidos. Revise os campos e tente novamente.";
  }

  if (status >= 500) {
    return "Servico de cartoes indisponivel no momento. Tente novamente em instantes.";
  }

  return apiMessage ?? genericMessage;
}

function parseWalletError(rawPayload: string): WalletApiError | null {
  if (!rawPayload) {
    return null;
  }

  try {
    return JSON.parse(rawPayload) as WalletApiError;
  } catch {
    return { message: rawPayload };
  }
}
