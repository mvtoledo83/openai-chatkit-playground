import { useEffect } from "react";
import { ChatKit, useChatKit } from "@openai/chatkit-react";
import {
  CARDS_CUSTOMER_ID,
  CHATKIT_API_DOMAIN_KEY,
  CHATKIT_API_URL,
} from "../lib/config";

export type JourneyId = 1 | 2 | 3;

const JOURNEY_COPY: Record<
  JourneyId,
  { eyebrow: string; heading: string; badge: string }
> = {
  1: {
    eyebrow: "Jornada 1 - Webcheckout Getnet",
    heading: "Pagamento via link do webcheckout",
    badge: "Botao Pagar + link",
  },
  2: {
    eyebrow: "Jornada 2 - Cartao salvo",
    heading: "Pagamento com cartao salvo no chat",
    badge: "Cartoes + pagamento",
  },
  3: {
    eyebrow: "Jornada 3 - Formulario de cartao",
    heading: "Pagamento com dados do cartao no chat",
    badge: "Formulario + R$ 0,01",
  },
};

type ChatKitPanelProps = {
  journey: JourneyId;
};

export function ChatKitPanel({ journey }: ChatKitPanelProps) {
  const journeyFetch: typeof fetch = (input, init) => {
    const headers = new Headers(init?.headers);
    headers.set("X-Journey", String(journey));
    return fetch(input, { ...init, headers });
  };

  const chatkit = useChatKit({
    api: {
      url: CHATKIT_API_URL,
      domainKey: CHATKIT_API_DOMAIN_KEY,
      fetch: journeyFetch,
    },
    composer: {
      // File uploads are disabled for the demo backend.
      attachments: { enabled: false },
    },
  });

  useEffect(() => {
    const timer = setTimeout(() => {
      void chatkit
        .sendCustomAction({
          type: "journey.select",
          payload: { journey, customerId: CARDS_CUSTOMER_ID },
        })
        .catch(() => {
          // The journey is also inferred from the X-Journey header, so a
          // failed auto-start (e.g. before a thread exists) is non-fatal.
        });
    }, 350);

    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [journey]);

  const journeyCopy = JOURNEY_COPY[journey];

  return (
    <div className="relative flex h-full min-h-[80vh] w-full flex-col overflow-hidden rounded-[2rem] border border-emerald-200/80 bg-white/92 shadow-[0_28px_80px_rgba(13,127,105,0.14)] backdrop-blur-xl">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-gradient-to-r from-emerald-100/80 via-white to-cyan-50/70" />
      <div className="relative flex items-center justify-between border-b border-emerald-100/90 px-6 py-5">
        <div>
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-emerald-700">
            {journeyCopy.eyebrow}
          </p>
          <h2 className="mt-2 text-xl font-semibold text-slate-900">
            {journeyCopy.heading}
          </h2>
        </div>
        <div className="rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-xs font-medium text-emerald-700">
          {journeyCopy.badge}
        </div>
      </div>

      <div className="relative flex-1 px-2 pb-2">
        <ChatKit control={chatkit.control} className="block h-full w-full rounded-[1.6rem] bg-transparent" />
      </div>
    </div>
  );
}
