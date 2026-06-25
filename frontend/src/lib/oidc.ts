import type { OidcConfiguration } from "@axa-fr/react-oidc";
import {
  OIDC_AUTHORITY,
  OIDC_CLIENT_ID,
  OIDC_POST_LOGOUT_REDIRECT_URI,
  OIDC_REDIRECT_URI,
  OIDC_SILENT_REDIRECT_URI,
  OIDC_SCOPE,
} from "./config";

export const oidcConfiguration: OidcConfiguration = {
  authority: OIDC_AUTHORITY,
  client_id: OIDC_CLIENT_ID,
  redirect_uri: OIDC_REDIRECT_URI,
  silent_redirect_uri: OIDC_SILENT_REDIRECT_URI,
  post_logout_redirect_uri: OIDC_POST_LOGOUT_REDIRECT_URI,
  scope: OIDC_SCOPE,
  service_worker_only: false,
};
