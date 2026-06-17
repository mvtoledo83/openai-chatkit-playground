type CheckoutDrawerProps = {
  open: boolean;
  title: string;
  subtitle?: string;
  redirectUrl?: string;
  status: string;
  error?: string | null;
  onClose: () => void;
  onFeedback: (status: "completed" | "cancelled" | "pending") => void;
  submittingFeedback?: boolean;
};

export function CheckoutDrawer({
  open,
  title,
  subtitle,
  redirectUrl,
  status,
  error,
  onClose,
  onFeedback,
  submittingFeedback = false,
}: CheckoutDrawerProps) {
  if (!open) {
    return null;
  }

  return (
    <section className="fixed inset-0 z-50 flex items-end justify-center bg-emerald-950/12 p-4 backdrop-blur-md md:items-center">
      <div className="flex h-[85vh] w-full max-w-5xl flex-col overflow-hidden rounded-[2rem] border border-emerald-200/70 bg-white shadow-[0_32px_90px_rgba(10,104,84,0.18)]">
        <header className="flex items-start justify-between gap-4 border-b border-emerald-100 bg-gradient-to-r from-emerald-50 via-white to-cyan-50/70 px-6 py-5 text-slate-900">
          <div>
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-emerald-700">
              Checkout
            </p>
            <h2 className="mt-2 text-2xl font-semibold">{title}</h2>
            {subtitle ? (
              <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-emerald-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-emerald-50"
          >
            Fechar
          </button>
        </header>

        <div className="flex items-center justify-between border-b border-emerald-100 bg-white px-6 py-3 text-sm text-slate-600">
          <span className="font-medium text-emerald-800">{status}</span>
          {error ? <span className="text-rose-600">{error}</span> : null}
        </div>

        <div className="flex-1 bg-[linear-gradient(180deg,#f9fcfb_0%,#ffffff_100%)] p-3 md:p-4">
          {redirectUrl ? (
            <iframe
              src={redirectUrl}
              title="Getnet Checkout"
              className="h-full w-full rounded-[1.5rem] border border-emerald-100 bg-white"
              allow="payment"
            />
          ) : (
            <div className="flex h-full items-center justify-center rounded-[1.5rem] border border-dashed border-emerald-200 bg-emerald-50/50 p-8 text-slate-500">
              Aguarde a criação da intenção de checkout.
            </div>
          )}
        </div>

        <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-emerald-100 bg-white px-6 py-4">
          <button
            type="button"
            onClick={() => onFeedback("pending")}
            disabled={submittingFeedback}
            className="rounded-full border border-sky-200 bg-white px-4 py-2 text-xs font-medium text-sky-800 transition hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Marcar como pendente
          </button>
          <button
            type="button"
            onClick={() => onFeedback("completed")}
            disabled={submittingFeedback}
            className="rounded-full bg-[linear-gradient(135deg,#0070c9,#0057a0)] px-4 py-2 text-xs font-semibold text-white shadow-[0_14px_30px_rgba(0,112,201,0.25)] transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Marcar como concluido
          </button>
          <button
            type="button"
            onClick={() => onFeedback("cancelled")}
            disabled={submittingFeedback}
            className="rounded-full border border-sky-200 bg-sky-50 px-4 py-2 text-xs font-medium text-sky-800 transition hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Marcar como cancelado
          </button>
        </footer>
      </div>
    </section>
  );
}