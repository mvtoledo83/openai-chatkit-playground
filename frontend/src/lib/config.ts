const readEnvString = (value: unknown): string | undefined =>
  typeof value === "string" && value.trim().length > 0
    ? value.trim()
    : undefined;

const readEnvBoolean = (value: unknown, defaultValue = false): boolean => {
  if (typeof value !== "string") {
    return defaultValue;
  }

  const normalized = value.trim().toLowerCase();
  return normalized === "1" || normalized === "true" || normalized === "yes";
};

export const CHATKIT_API_URL =
  readEnvString(import.meta.env.VITE_CHATKIT_API_URL) ?? "/chatkit";

export const CHECKOUT_API_URL =
  readEnvString(import.meta.env.VITE_CHECKOUT_API_URL) ?? "/checkout/intents";

export const MS_AGENTIC_COMMERCE_URL =
  readEnvString(import.meta.env.VITE_MS_AGENTIC_COMMERCE_URL) ??
  "https://api.app.dev.gms.corp/gai/agentic-commerce/v1";

export const CARDS_REAL_MODE =
  readEnvBoolean(import.meta.env.VITE_ENABLE_CARDS_API);

export const CARDS_API_URL =
  readEnvString(import.meta.env.VITE_CARDS_API_URL) ?? "/wallet/cards";

export const CARDS_CUSTOMER_ID =
  readEnvString(import.meta.env.VITE_CARDS_CUSTOMER_ID) ?? "017";

export const CARDS_TOKEN_URL =
  readEnvString(import.meta.env.VITE_CARDS_TOKEN_URL) ?? "/wallet/token";

export const OIDC_ENABLED = readEnvBoolean(import.meta.env.VITE_ENABLE_OIDC);

const FRONTEND_ORIGIN =
  typeof window !== "undefined" ? window.location.origin : "http://localhost:8080";

export const OIDC_AUTHORITY =
  readEnvString(import.meta.env.VITE_AUTH_AUTHORITY) ??
  readEnvString(import.meta.env.VITE_OIDC_AUTHORITY) ??
  "https://am.infra.dev.gms.corp/oauth2/SanAzureAd";

export const OIDC_CLIENT_ID =
  readEnvString(import.meta.env.VITE_AUTH_CLIENT_ID) ??
  readEnvString(import.meta.env.VITE_OIDC_CLIENT_ID) ??
  "agenticCommerce";

export const OIDC_SCOPE =
  readEnvString(import.meta.env.VITE_AUTH_SCOPE) ??
  readEnvString(import.meta.env.VITE_OIDC_SCOPE) ??
  "openid profile";

export const OIDC_REDIRECT_URI =
  readEnvString(import.meta.env.VITE_AUTH_REDIRECT_URI) ??
  `${FRONTEND_ORIGIN}/authentication/callback`;

export const OIDC_SILENT_REDIRECT_URI =
  readEnvString(import.meta.env.VITE_AUTH_SILENT_REDIRECT_URI) ??
  `${FRONTEND_ORIGIN}/authentication/silent_callback`;

export const OIDC_POST_LOGOUT_REDIRECT_URI =
  readEnvString(import.meta.env.VITE_AUTH_LOGOUT_REDIRECT_URL) ??
  readEnvString(import.meta.env.VITE_OIDC_POST_LOGOUT_REDIRECT_PATH) ??
  `${FRONTEND_ORIGIN}/`;

/**
 * ChatKit requires a domain key at runtime. Use the local fallback while
 * developing, and register a production domain key for deployment:
 * https://platform.openai.com/settings/organization/security/domain-allowlist
 */
export const CHATKIT_API_DOMAIN_KEY =
  readEnvString(import.meta.env.VITE_CHATKIT_API_DOMAIN_KEY) ??
  "domain_pk_localhost_dev";
