import { ChatKitPanel } from "./components/ChatKitPanel";

export default function App() {
  return (
    <main className="sanitas-shell min-h-screen">
      <section className="mx-auto flex min-h-screen w-full max-w-none flex-col px-3 py-5 md:px-6 md:py-6">
        <div className="min-h-[90vh] w-full">
          <ChatKitPanel />
        </div>
      </section>
    </main>
  );
}
