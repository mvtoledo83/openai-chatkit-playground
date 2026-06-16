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
};

export function ChatKitPanel() {
  const lastOpenedCheckoutId = useRef<string | null>(null);

  const [checkoutState, setCheckoutState] = useState<CheckoutState>({
    title: "Checkout",
    subtitle: "",
    status: "Pronto para iniciar",
    open: false,
  });

  useEffect(() => {
    void (async () => {
      const latestCheckout = await getLatestCheckout();
      if (latestCheckout?.payment_intent_id) {
        lastOpenedCheckoutId.current = latestCheckout.payment_intent_id;
      }
    })();
  }, []);

  const openCheckoutFromThread = (checkout: LatestThreadCheckout) => {
    setCheckoutState({
      title: "Checkout",
      subtitle: `Flow ${checkout.flow}`,
      status: `Checkout criado: ${checkout.payment_intent_id}`,
      redirectUrl: checkout.redirect_url,
      open: true,
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

        if (lastOpenedCheckoutId.current === latestCheckout.payment_intent_id) {
          return;
        }

        lastOpenedCheckoutId.current = latestCheckout.payment_intent_id;
        openCheckoutFromThread(latestCheckout);
      })();
    },
  });

  return (
    <>
      <div className="relative flex h-[90vh] w-full flex-col overflow-hidden rounded-2xl bg-white pb-8 shadow-sm transition-colors dark:bg-slate-900">
        <ChatKit control={chatkit.control} className="block h-full w-full" />
      </div>

      <CheckoutDrawer
        open={checkoutState.open}
        title={checkoutState.title}
        subtitle={checkoutState.subtitle}
        status={checkoutState.status}
        redirectUrl={checkoutState.redirectUrl}
        error={checkoutState.error}
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
