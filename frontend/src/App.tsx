import { useCallback, useEffect, useState } from "react";
import { ChatKitPanel, type JourneyId } from "./components/ChatKitPanel";
import { AppHeader } from "./components/layout/AppHeader";
import { AppSidebar, type AppSection } from "./components/layout/AppSidebar";
import { CardRegistrationModal } from "./components/modals/CardRegistrationModal";
import { CheckoutDrawer } from "./components/CheckoutDrawer";
import { createCardRegistrationIntent } from "./lib/checkout";
import {
  getSavedCards,
  deleteCard,
  type CardRegistrationResult,
  type SavedCardSummary,
} from "./lib/cards";
import { CARDS_CUSTOMER_ID, CARDS_REAL_MODE } from "./lib/config";

const CARDS_CUSTOMER_ID_STORAGE_KEY = "wallet.customerId";

type IframeRegistrationState = {
  open: boolean;
  loading: boolean;
  redirectUrl?: string;
  status: string;
  error?: string | null;
};

const INITIAL_IFRAME_REGISTRATION: IframeRegistrationState = {
  open: false,
  loading: false,
  status: "Pronto para iniciar",
};

const JOURNEY_SECTIONS: Record<
  Exclude<AppSection, "cards">,
  JourneyId
> = {
  journey1: 1,
  journey2: 2,
  journey3: 3,
};

function readStoredCustomerId(): string {
  if (typeof window === "undefined") {
    return CARDS_CUSTOMER_ID;
  }
  const stored = window.localStorage.getItem(CARDS_CUSTOMER_ID_STORAGE_KEY);
  return stored?.trim() ? stored.trim() : CARDS_CUSTOMER_ID;
}

export default function App() {
  const [activeSection, setActiveSection] = useState<AppSection>("journey1");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [cardModalOpen, setCardModalOpen] = useState(false);
  const [cardSavedNotice, setCardSavedNotice] = useState<string | null>(null);
  const [savedCards, setSavedCards] = useState<SavedCardSummary[]>([]);
  const [cardsLoading, setCardsLoading] = useState(false);
  const [cardsError, setCardsError] = useState<string | null>(null);
  const [deletingCardId, setDeletingCardId] = useState<string | null>(null);
  const [listCustomerId, setListCustomerId] = useState(readStoredCustomerId);

  const [iframeRegistration, setIframeRegistration] =
    useState<IframeRegistrationState>(INITIAL_IFRAME_REGISTRATION);

  const openCardModal = () => {
    setCardSavedNotice(null);
    setCardModalOpen(true);
  };

  const openIframeRegistration = async () => {
    setIframeRegistration({
      open: true,
      loading: true,
      status: "Gerando iframe de cadastro na GetNet...",
      error: null,
    });

    try {
      const intent = await createCardRegistrationIntent();
      setIframeRegistration({
        open: true,
        loading: false,
        redirectUrl: intent.redirect_url,
        status: `Cadastro de cartao iniciado: ${intent.payment_intent_id}`,
        error: null,
      });
    } catch (error) {
      setIframeRegistration({
        open: true,
        loading: false,
        status: "Falha ao iniciar o cadastro via iframe.",
        error:
          error instanceof Error
            ? error.message
            : "Nao foi possivel iniciar o cadastro via iframe.",
      });
    }
  };

  const closeIframeRegistration = () => {
    setIframeRegistration(INITIAL_IFRAME_REGISTRATION);
  };

  const handleIframeRegistrationFeedback = (
    status: "completed" | "cancelled" | "pending",
  ) => {
    if (status === "completed") {
      setCardSavedNotice("Cadastro de cartao via iframe concluido.");
      setActiveSection("cards");
      if (CARDS_REAL_MODE) {
        void loadCards();
      }
    }
    closeIframeRegistration();
  };

  const handleDeleteCard = async (cardId: string) => {
    try {
      setDeletingCardId(cardId);
      setCardsError(null);
      await deleteCard(cardId);
      setSavedCards((current) => current.filter((c) => c.id !== cardId));
      setCardSavedNotice("Cartão deletado com sucesso.");
    } catch (error) {
      setCardsError(
        error instanceof Error
          ? error.message
          : "Não foi possível deletar o cartão.",
      );
    } finally {
      setDeletingCardId(null);
    }
  };

  const loadCards = useCallback(
    async (customerIdOverride?: string) => {
      if (!CARDS_REAL_MODE) {
        return;
      }

      const targetCustomerId =
        (customerIdOverride ?? listCustomerId).trim() || CARDS_CUSTOMER_ID;

      try {
        setCardsLoading(true);
        setCardsError(null);
        const cards = await getSavedCards(targetCustomerId);
        setSavedCards(cards);
      } catch (error) {
        setCardsError(
          error instanceof Error
            ? error.message
            : "Nao foi possivel carregar cartoes salvos.",
        );
      } finally {
        setCardsLoading(false);
      }
    },
    [listCustomerId],
  );

  useEffect(() => {
    if (activeSection !== "cards") {
      return;
    }

    void loadCards();
  }, [activeSection, loadCards]);

  const handleCardSaved = (savedCard: CardRegistrationResult) => {
    if (!CARDS_REAL_MODE) {
      setSavedCards((current) => [
        {
          id: savedCard.cardId,
          label: savedCard.label,
          brand: savedCard.brand,
          last4: savedCard.last4,
          cardholderName: savedCard.cardholderName,
        },
        ...current,
      ]);
    }

    setCardSavedNotice(`Cartao '${savedCard.label}' cadastrado com sucesso.`);
    setActiveSection("cards");

    if (CARDS_REAL_MODE) {
      const savedCustomerId = savedCard.customerId.trim() || CARDS_CUSTOMER_ID;
      setListCustomerId(savedCustomerId);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(
          CARDS_CUSTOMER_ID_STORAGE_KEY,
          savedCustomerId,
        );
      }
      void loadCards(savedCustomerId);
    }
  };

  return (
    <main className="sanitas-shell flex min-h-screen flex-col">
      <AppHeader
        onOpenCardModal={openCardModal}
        onOpenIframeRegistration={() => {
          void openIframeRegistration();
        }}
        onOpenSidebar={() => setMobileSidebarOpen(true)}
      />

      <section className="mx-auto flex min-h-0 w-full max-w-none flex-1 px-3 pb-4 pt-3 md:px-6 md:pb-6 md:pt-4">
        <div className="flex min-h-0 w-full gap-3 md:gap-4">
          <AppSidebar
            activeSection={activeSection}
            mobileOpen={mobileSidebarOpen}
            onCloseMobile={() => setMobileSidebarOpen(false)}
            onSelectSection={(section) => {
              setActiveSection(section);
              setMobileSidebarOpen(false);
            }}
          />

          <div className="min-h-0 flex-1 overflow-hidden">
            {activeSection === "cards" ? (
              <section className="relative flex h-full min-h-[80vh] w-full flex-col overflow-hidden rounded-[2rem] border border-emerald-200/80 bg-white/92 p-6 shadow-[0_28px_80px_rgba(13,127,105,0.14)] backdrop-blur-xl md:p-8">
                <div className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-gradient-to-r from-emerald-100/80 via-white to-cyan-50/70" />
                <div className="relative">
                  <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-emerald-700">
                    Cartoes salvos
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold text-slate-900">
                    Gerencie seus cartoes cadastrados
                  </h2>
                  <p className="mt-2 max-w-2xl text-sm text-slate-600">
                    Esta area esta preparada para listar os cartoes quando o
                    servico da GetNet for conectado.
                  </p>
                </div>

                <div className="relative mt-8 flex flex-1 items-center justify-center rounded-[1.5rem] border border-dashed border-emerald-200 bg-emerald-50/55 p-8 text-center">
                  {cardsLoading ? (
                    <div>
                      <p className="text-base font-medium text-emerald-900">
                        Carregando cartoes salvos...
                      </p>
                    </div>
                  ) : cardsError ? (
                    <div>
                      <p className="text-base font-medium text-rose-700">
                        {cardsError}
                      </p>
                      <button
                        type="button"
                        onClick={() => {
                          void loadCards();
                        }}
                        className="mt-3 rounded-full border border-emerald-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-emerald-50"
                      >
                        Tentar novamente
                      </button>
                    </div>
                  ) : savedCards.length > 0 ? (
                    <div className="w-full max-w-3xl space-y-3 text-left">
                      {savedCards.map((savedCard) => (
                        <article
                          key={savedCard.id}
                          className="rounded-2xl border border-emerald-200 bg-white px-4 py-3 shadow-[0_10px_26px_rgba(13,127,105,0.08)]"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex-1">
                              <p className="text-sm font-semibold text-slate-900">
                                {savedCard.label}
                              </p>
                              <p className="mt-1 text-sm text-slate-600">
                                Titular: {savedCard.cardholderName}
                              </p>
                              <p className="mt-1 text-xs text-slate-500">
                                Final {savedCard.last4}
                              </p>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-800">
                                {savedCard.brand}
                              </span>
                              <button
                                type="button"
                                onClick={() => {
                                  void handleDeleteCard(savedCard.id);
                                }}
                                disabled={deletingCardId === savedCard.id}
                                className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-xs font-medium text-rose-700 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60"
                              >
                                {deletingCardId === savedCard.id ? "Deletando..." : "Deletar"}
                              </button>
                            </div>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div>
                      <p className="text-base font-medium text-emerald-900">
                        Nenhum cartao exibido nesta versao
                      </p>
                      <p className="mt-2 text-sm text-slate-600">
                        Use o botao no cabecalho para cadastrar seu primeiro
                        cartao.
                      </p>
                    </div>
                  )}
                </div>

                {cardSavedNotice ? (
                  <p className="relative mt-4 rounded-full border border-emerald-200 bg-white px-4 py-2 text-sm text-emerald-800">
                    {cardSavedNotice}
                  </p>
                ) : null}
              </section>
            ) : (
              <ChatKitPanel
                key={activeSection}
                journey={JOURNEY_SECTIONS[activeSection]}
              />
            )}
          </div>
        </div>
      </section>

      <CardRegistrationModal
        open={cardModalOpen}
        onClose={() => setCardModalOpen(false)}
        onSaved={handleCardSaved}
      />

      <CheckoutDrawer
        open={iframeRegistration.open}
        title="Cadastro de cartao (iframe GetNet)"
        subtitle="Os dados do cartao sao capturados na pagina hospedada da GetNet."
        redirectUrl={iframeRegistration.redirectUrl}
        status={
          iframeRegistration.loading
            ? "Gerando iframe de cadastro na GetNet..."
            : iframeRegistration.status
        }
        error={iframeRegistration.error}
        onClose={closeIframeRegistration}
        onFeedback={handleIframeRegistrationFeedback}
      />
    </main>
  );
}
