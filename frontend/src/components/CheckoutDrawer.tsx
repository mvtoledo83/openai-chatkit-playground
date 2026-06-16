type CheckoutDrawerProps = {
  open: boolean;
  title: string;
  subtitle?: string;
  redirectUrl?: string;
  status: string;
  error?: string | null;
  onClose: () => void;
};

export function CheckoutDrawer({
  open,
  title,
  subtitle,
  redirectUrl,
  status,
  error,
  onClose,
}: CheckoutDrawerProps) {
  if (!open) {
    return null;
  }

  return (
    <section className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/50 p-4 backdrop-blur-sm md:items-center">
      <div className="flex h-[85vh] w-full max-w-5xl flex-col overflow-hidden rounded-3xl border border-white/10 bg-slate-950 shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-white/10 px-5 py-4 text-white">
          <div>
            <p className="text-sm uppercase tracking-[0.25em] text-cyan-300">
              Checkout
            </p>
            <h2 className="mt-2 text-xl font-semibold">{title}</h2>
            {subtitle ? (
              <p className="mt-1 text-sm text-slate-300">{subtitle}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-white/15 px-4 py-2 text-sm text-white transition hover:bg-white/10"
          >
            Fechar
          </button>
        </header>

        <div className="flex items-center justify-between border-b border-white/10 bg-slate-900 px-5 py-3 text-sm text-slate-300">
          <span>{status}</span>
          {error ? <span className="text-rose-300">{error}</span> : null}
        </div>

        <div className="flex-1 bg-white">
          {redirectUrl ? (
            <iframe
              src={redirectUrl}
              title="Getnet Checkout"
              className="h-full w-full border-0"
              allow="payment"
            />
          ) : (
            <div className="flex h-full items-center justify-center p-8 text-slate-500">
              Aguarde a criação da intenção de checkout.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}