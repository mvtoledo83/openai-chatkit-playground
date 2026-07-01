export type AppSection =
  | "journey1"
  | "journey2"
  | "journey3"
  | "cards";

type SidebarItem = {
  id: AppSection;
  label: string;
  helper: string;
};

type SidebarGroup = {
  title: string;
  items: SidebarItem[];
};

type AppSidebarProps = {
  activeSection: AppSection;
  mobileOpen: boolean;
  onCloseMobile: () => void;
  onSelectSection: (section: AppSection) => void;
};

const GROUPS: SidebarGroup[] = [
  {
    title: "Jornadas",
    items: [
      {
        id: "journey1",
        label: "Jornada 1",
        helper: "Botao Pagar + link do webcheckout Getnet",
      },
      {
        id: "journey2",
        label: "Jornada 2",
        helper: "Cartao salvo + pagamento no chat",
      },
      {
        id: "journey3",
        label: "Jornada 3",
        helper: "Formulario de cartao no chat (R$ 0,01)",
      },
    ],
  },
  {
    title: "Cartoes",
    items: [
      {
        id: "cards",
        label: "Cartoes salvos",
        helper: "Gerenciar cartoes cadastrados",
      },
    ],
  },
];

const sidebarPanelClassName =
  "flex h-full w-[17.5rem] flex-col overflow-hidden rounded-[1.6rem] border border-emerald-200/80 bg-white/88 shadow-[0_20px_60px_rgba(13,127,105,0.12)] backdrop-blur-xl";

export function AppSidebar({
  activeSection,
  mobileOpen,
  onCloseMobile,
  onSelectSection,
}: AppSidebarProps) {
  return (
    <>
      <aside className="hidden min-h-0 md:block">
        <SidebarContent
          activeSection={activeSection}
          onSelectSection={onSelectSection}
        />
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-40 flex bg-emerald-950/22 backdrop-blur-sm md:hidden">
          <div className="w-[84vw] max-w-xs p-3">
            <div className={sidebarPanelClassName}>
              <SidebarContent
                activeSection={activeSection}
                onSelectSection={onSelectSection}
              />
            </div>
          </div>
          <button
            type="button"
            onClick={onCloseMobile}
            className="flex-1"
            aria-label="Fechar menu lateral"
          />
        </div>
      ) : null}
    </>
  );
}

type SidebarContentProps = {
  activeSection: AppSection;
  onSelectSection: (section: AppSection) => void;
};

function SidebarContent({ activeSection, onSelectSection }: SidebarContentProps) {
  return (
    <div className={sidebarPanelClassName}>
      <div className="border-b border-emerald-100/90 px-4 py-4">
        <p className="text-[0.65rem] font-semibold uppercase tracking-[0.26em] text-emerald-700">
          Navegacao
        </p>
        <p className="mt-2 text-sm text-slate-600">Areas da aplicacao</p>
      </div>

      <nav className="flex-1 space-y-4 overflow-y-auto px-3 py-3">
        {GROUPS.map((group) => (
          <div key={group.title} className="space-y-2">
            <p className="px-2 text-[0.62rem] font-semibold uppercase tracking-[0.24em] text-emerald-600/90">
              {group.title}
            </p>
            {group.items.map((item) => {
              const active = item.id === activeSection;

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSelectSection(item.id)}
                  className={[
                    "w-full rounded-2xl border px-3 py-3 text-left transition",
                    active
                      ? "border-emerald-200 bg-emerald-50/90"
                      : "border-transparent bg-white hover:border-emerald-100 hover:bg-emerald-50/45",
                  ].join(" ")}
                >
                  <p className="text-sm font-semibold text-slate-900">
                    {item.label}
                  </p>
                  <p className="mt-1 text-xs text-slate-600">{item.helper}</p>
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="border-t border-emerald-100/90 bg-emerald-50/45 px-4 py-4">
        <p className="text-xs text-emerald-900">Sandbox de pagamentos preparado</p>
      </div>
    </div>
  );
}
