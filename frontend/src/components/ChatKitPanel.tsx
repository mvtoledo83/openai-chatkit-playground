import { useEffect, useRef, useState } from "react";
import { ChatKit, useChatKit } from "@openai/chatkit-react";
import {
  getLatestCheckout,
  type LatestThreadCheckout,
} from "../lib/checkout";
import { CHATKIT_API_DOMAIN_KEY, CHATKIT_API_URL } from "../lib/config";
import { CheckoutDrawer } from "./CheckoutDrawer";

type CheckoutState = {
  title: string;
  subtitle: string;
  status: string;
  redirectUrl?: string;
  error?: string | null;
  open: boolean;
  paymentIntentId?: string;
};

export function ChatKitPanel() {
  const lastOpenedCheckoutId = useRef<string | null>(null);
  const [submittingFeedback, setSubmittingFeedback] = useState(false);

  const [checkoutState, setCheckoutState] = useState<CheckoutState>({
    title: "Checkout",
    subtitle: "",
    status: "Pronto para iniciar",
    open: false,
  });

  useEffect(() => {
    void (async () => {
      const latestCheckout = await getLatestCheckout();
      if (!latestCheckout?.payment_intent_id) {
        return;
      }

      if (latestCheckout.status === "created") {
        lastOpenedCheckoutId.current = latestCheckout.payment_intent_id;
        openCheckoutFromThread(latestCheckout);
        return;
      }

      lastOpenedCheckoutId.current = latestCheckout.payment_intent_id;
    })();
  }, []);

  const openCheckoutFromThread = (checkout: LatestThreadCheckout) => {
    setCheckoutState({
      title: "Checkout final",
      subtitle: `Flow ${checkout.flow}`,
      status: `Checkout criado: ${checkout.payment_intent_id}`,
      redirectUrl: checkout.redirect_url,
      open: true,
      paymentIntentId: checkout.payment_intent_id,
    });
  };

  const chatkit = useChatKit({
    api: { url: CHATKIT_API_URL, domainKey: CHATKIT_API_DOMAIN_KEY },
    composer: {
      // File uploads are disabled for the demo backend.
      attachments: { enabled: false },
    },
    onResponseEnd: () => {
      void (async () => {
        const latestCheckout = await getLatestCheckout();
        if (!latestCheckout) {
          return;
        }

        if (latestCheckout.status && latestCheckout.status !== "created") {
          return;
        }

        if (lastOpenedCheckoutId.current === latestCheckout.payment_intent_id) {
          return;
        }

        lastOpenedCheckoutId.current = latestCheckout.payment_intent_id;
        openCheckoutFromThread(latestCheckout);
      })();
    },
  });

  const submitIframeFeedback = async (
    feedbackStatus: "completed" | "cancelled" | "pending",
  ) => {
    if (!checkoutState.paymentIntentId) {
      setCheckoutState((current) => ({
        ...current,
        error: "Nao foi possivel identificar o checkout ativo.",
      }));
      return;
    }

    try {
      setSubmittingFeedback(true);
      await chatkit.sendCustomAction({
        type: "checkout.iframe.feedback",
        payload: {
          status: feedbackStatus,
          payment_intent_id: checkoutState.paymentIntentId,
        },
      });
      setCheckoutState((current) => ({
        ...current,
        open: false,
        error: null,
      }));
    } catch {
      setCheckoutState((current) => ({
        ...current,
        error: "Falha ao enviar status para o chat.",
      }));
    } finally {
      setSubmittingFeedback(false);
    }
  };

  return (
    <>
      <div className="relative flex h-full min-h-[80vh] w-full flex-col overflow-hidden rounded-[2rem] border border-emerald-200/80 bg-white/92 shadow-[0_28px_80px_rgba(13,127,105,0.14)] backdrop-blur-xl">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-gradient-to-r from-emerald-100/80 via-white to-cyan-50/70" />
        <div className="relative flex items-center justify-between border-b border-emerald-100/90 px-6 py-5">
          <div>
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-emerald-700">
              Assistente de checkout
            </p>
            <h2 className="mt-2 text-xl font-semibold text-slate-900">
              Fluxo guiado em conversa
            </h2>
          </div>
          <div className="rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-xs font-medium text-emerald-700">
            3 jornadas ativas
          </div>
        </div>

        <div className="relative flex-1 px-2 pb-2">
          <ChatKit control={chatkit.control} className="block h-full w-full rounded-[1.6rem] bg-transparent" />
        </div>
      </div>

      <CheckoutDrawer
        open={checkoutState.open}
        title={checkoutState.title}
        subtitle={checkoutState.subtitle}
        status={checkoutState.status}
        redirectUrl={checkoutState.redirectUrl}
        error={checkoutState.error}
        submittingFeedback={submittingFeedback}
        onFeedback={(status) => {
          void submitIframeFeedback(status);
        }}
        onClose={() =>
          setCheckoutState((current) => ({
            ...current,
            open: false,
          }))
        }
      />
    </>
  );
}
