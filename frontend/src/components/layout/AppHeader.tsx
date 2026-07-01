type AppHeaderProps = {
  onOpenCardModal: () => void;
  onOpenIframeRegistration: () => void;
  onOpenSidebar: () => void;
};

export function AppHeader({
  onOpenCardModal,
  onOpenIframeRegistration,
  onOpenSidebar,
}: AppHeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-emerald-200/80 bg-white/88 backdrop-blur-xl">
      <div className="mx-auto flex h-16 w-full max-w-none items-center justify-between px-3 md:px-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onOpenSidebar}
            className="inline-flex items-center justify-center rounded-xl border border-emerald-200 bg-white px-3 py-2 text-xs font-semibold text-emerald-800 transition hover:bg-emerald-50 md:hidden"
            aria-label="Abrir menu lateral"
          >
            Menu
          </button>
          <div>
            <p className="text-[0.66rem] font-semibold uppercase tracking-[0.26em] text-emerald-700">
              OpenAI ChatKit Playground
            </p>
            <h1 className="text-sm font-semibold text-slate-900 md:text-base">
              Checkout Assistant Workspace
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2 md:gap-3">
          <button
            type="button"
            onClick={onOpenIframeRegistration}
            className="rounded-full border border-[#0068b4]/40 bg-white px-4 py-2 text-xs font-semibold text-[#0068b4] shadow-[0_10px_24px_rgba(0,104,180,0.16)] transition hover:bg-[#eef6fc] md:px-5 md:text-sm"
          >
            Cadastrar via iframe
          </button>
          <button
            type="button"
            onClick={onOpenCardModal}
            className="rounded-full bg-[linear-gradient(135deg,#0089c7,#0068b4)] px-4 py-2 text-xs font-semibold text-white shadow-[0_14px_30px_rgba(0,104,180,0.26)] transition hover:brightness-105 md:px-5 md:text-sm"
          >
            Cadastrar cartao
          </button>
        </div>
      </div>
    </header>
  );
}
