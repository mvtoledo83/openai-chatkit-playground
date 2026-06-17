import { CHECKOUT_API_URL } from "./config";

export type CheckoutFlow = "payment" | "ai_agent" | "card_verification";

export type CheckoutIntentRequest = {
  flow: CheckoutFlow;
  order_id: string;
  country?: string;
  checkout_type?: string;
  customer: {
    customer_id: string;
    name: string;
    first_name: string;
    last_name: string;
    email: string;
    checked_email?: boolean;
    document_type: string;
    document_number: string;
    phone_number: string;
    billing_address: {
      street: string;
      number: string;
      country: string;
      postal_code: string;
      district: string;
      city: string;
      state: string;
      complement?: string;
    };
  };
  payment?: {
    currency: string;
    amount: number;
  };
  product?: Array<{
    product_type?: string;
    title: string;
    value: number;
    quantity?: number;
  }>;
  shipping?: {
    first_name: string;
    last_name: string;
    name: string;
    phone_number: string;
    address: {
      street: string;
      number: string;
      country: string;
      postal_code: string;
      district: string;
      city: string;
      state: string;
    };
  };
};

export type CheckoutIntentResponse = {
  payment_intent_id: string;
  trade_name?: string | null;
  redirect_url: string;
  access_token?: string | null;
  flow: CheckoutFlow;
};

export type LatestThreadCheckout = {
  payment_intent_id: string;
  redirect_url: string;
  flow: CheckoutFlow;
  status?: "created" | "completed" | "cancelled" | "pending" | string;
  updated_at: string;
};

export async function createCheckoutIntent(
  checkoutRequest: CheckoutIntentRequest,
): Promise<CheckoutIntentResponse> {
  const response = await fetch(CHECKOUT_API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(checkoutRequest),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `Checkout intent failed with ${response.status}`);
  }

  return (await response.json()) as CheckoutIntentResponse;
}

export async function getLatestThreadCheckout(
  threadId: string,
): Promise<LatestThreadCheckout | null> {
  const response = await fetch(
    `/checkout/threads/${encodeURIComponent(threadId)}/latest`,
  );

  if (!response.ok) {
    return null;
  }

  const payload = (await response.json()) as {
    latest_checkout?: LatestThreadCheckout | null;
  };

  return payload.latest_checkout ?? null;
}

export async function getLatestCheckout(): Promise<LatestThreadCheckout | null> {
  const response = await fetch(`/checkout/latest`);

  if (!response.ok) {
    return null;
  }

  const payload = (await response.json()) as {
    latest_checkout?: LatestThreadCheckout | null;
  };

  return payload.latest_checkout ?? null;
}