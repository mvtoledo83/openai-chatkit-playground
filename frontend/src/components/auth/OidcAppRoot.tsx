import { useEffect, useState } from "react";
import { OidcProvider } from "@axa-fr/react-oidc";
import App from "../../App";
import { OIDC_AUTHORITY, OIDC_CLIENT_ID, OIDC_ENABLED } from "../../lib/config";
import { oidcConfiguration } from "../../lib/oidc";

const oidcClientConfigured =
  OIDC_CLIENT_ID.length > 0 && OIDC_CLIENT_ID !== "SEU_CLIENT_ID";

export function OidcAppRoot() {
  const [authorityReachable, setAuthorityReachable] = useState<boolean | null>(
    OIDC_ENABLED && oidcClientConfigured ? null : false,
  );

  useEffect(() => {
    if (!OIDC_ENABLED || !oidcClientConfigured) {
      return;
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 4000);

    void fetch(`${OIDC_AUTHORITY}/.well-known/openid-configuration`, {
      method: "GET",
      signal: controller.signal,
      cache: "no-store",
    })
      .then((response) => {
        setAuthorityReachable(response.ok);
      })
      .catch(() => {
        setAuthorityReachable(false);
      })
      .finally(() => {
        clearTimeout(timeout);
      });

    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, []);

  if (!OIDC_ENABLED) {
    return <App />;
  }

  if (!oidcClientConfigured) {
    return (
      <>
        <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-900">
          OIDC habilitado, mas VITE_OIDC_CLIENT_ID esta ausente ou com valor placeholder.
        </div>
        <App />
      </>
    );
  }

  if (authorityReachable === null) {
    return <AuthLoading />;
  }

  if (!authorityReachable) {
    return (
      <>
        <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-900">
          Nao foi possivel conectar ao authority OIDC. Usando fallback sem login automatico.
        </div>
        <App />
      </>
    );
  }

  return (
    <OidcProvider
      configuration={oidcConfiguration}
      authenticatingComponent={AuthLoading}
      callbackSuccessComponent={AuthCallbackSuccess}
      callbackErrorComponent={AuthCallbackError}
    >
      <App />
    </OidcProvider>
  );
}

function AuthLoading() {
  return <div className="p-6 text-sm text-slate-600">Autenticando...</div>;
}

function AuthCallbackSuccess() {
  return <div className="p-6 text-sm text-slate-600">Login concluido. Carregando...</div>;
}

function AuthCallbackError() {
  return (
    <div className="p-6 text-sm text-rose-600">
      Falha na autenticacao OIDC. Verifique conectividade com o authority e as redirect URIs.
    </div>
  );
}
