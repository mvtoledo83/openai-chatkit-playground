import { useMemo, useState } from "react";
import {
  registerCard,
  type CardRegistrationResult,
} from "../../lib/cards";

type CardRegistrationModalProps = {
  open: boolean;
  onClose: () => void;
  onSaved: (savedCard: CardRegistrationResult) => void;
};

type FormState = {
  label: string;
  cardholderName: string;
  customerId: string;
  cardNumber: string;
  expiry: string;
  cvv: string;
};

type CardBrand = {
  id: string;
  label: string;
  numberLengths: number[];
  isMatch: (digits: string) => boolean;
};

const CARD_BRANDS: CardBrand[] = [
  {
    id: "visa",
    label: "Visa",
    numberLengths: [13, 16, 19],
    isMatch: (digits) => /^4/.test(digits),
  },
  {
    id: "mastercard",
    label: "Mastercard",
    numberLengths: [16],
    isMatch: (digits) => {
      if (!/^\d{1,16}$/.test(digits)) {
        return false;
      }

      const firstTwo = Number(digits.slice(0, 2));
      const firstFour = Number(digits.slice(0, 4));
      return (
        (firstTwo >= 51 && firstTwo <= 55) ||
        (firstFour >= 2221 && firstFour <= 2720)
      );
    },
  },
  {
    id: "amex",
    label: "Amex",
    numberLengths: [15],
    isMatch: (digits) => /^3[47]/.test(digits),
  },
  {
    id: "elo",
    label: "Elo",
    numberLengths: [16],
    isMatch: (digits) => /^(4011|4312|4389|4514|4576|5041|5090|6277|6362|6363)/.test(digits),
  },
  {
    id: "hipercard",
    label: "Hipercard",
    numberLengths: [16],
    isMatch: (digits) => /^6062/.test(digits),
  },
  {
    id: "discover",
    label: "Discover",
    numberLengths: [16],
    isMatch: (digits) => /^(6011|65)/.test(digits),
  },
];

const INITIAL_FORM: FormState = {
  label: "",
  cardholderName: "",
  customerId: "",
  cardNumber: "",
  expiry: "",
  cvv: "",
};

export function CardRegistrationModal({
  open,
  onClose,
  onSaved,
}: CardRegistrationModalProps) {
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const normalizedNumber = useMemo(
    () => form.cardNumber.replace(/\D/g, ""),
    [form.cardNumber],
  );
  const normalizedCustomerId = useMemo(
    () => form.customerId.trim(),
    [form.customerId],
  );
  const detectedBrand = useMemo(
    () => detectCardBrand(normalizedNumber),
    [normalizedNumber],
  );

  if (!open) {
    return null;
  }

  const validateForm = (): string | null => {
    if (form.customerId.trim().length < 1 || form.customerId.trim().length > 50) {
      return "Informe um ID de cliente (1 a 50 caracteres).";
    }

    if (normalizedNumber.length < 13 || normalizedNumber.length > 19) {
      return "Numero do cartao deve ter entre 13 e 19 digitos.";
    }

    if (!detectedBrand) {
      return "Nao foi possivel identificar a bandeira do cartao.";
    }

    if (
      detectedBrand &&
      !detectedBrand.numberLengths.includes(normalizedNumber.length)
    ) {
      return `Numero invalido para ${detectedBrand.label}.`;
    }

    if (!/^(0[1-9]|1[0-2])\/\d{2}$/.test(form.expiry)) {
      return "Validade invalida. Use o formato MM/YY.";
    }

    if (!/^\d{3,4}$/.test(form.cvv)) {
      return "CVV invalido. Use 3 ou 4 digitos.";
    }

    const [monthText, yearText] = form.expiry.split("/");
    const month = Number(monthText);
    const yearFull = Number(yearText) + 2000;
    const now = new Date();
    const currentMonth = now.getMonth() + 1;
    const currentYear = now.getFullYear();

    if (
      yearFull < currentYear ||
      (yearFull === currentYear && month < currentMonth)
    ) {
      return "Validade nao pode estar no passado.";
    }

    return null;
  };

  const submit = async () => {
    setError(null);
    setSuccess(null);

    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    const [monthText, yearText] = form.expiry.split("/");
    const month = Number(monthText);
    const year = Number(yearText);
    const brand = detectedBrand?.id;

    if (!brand) {
      setError("Nao foi possivel identificar a bandeira do cartao.");
      return;
    }

    try {
      setLoading(true);
      const result = await registerCard({
        label: form.label.trim(),
        cardNumber: normalizedNumber,
        brand,
        cardholderName: form.cardholderName.trim(),
        customerId: normalizedCustomerId,
        expiryMonth: month,
        expiryYear: year,
        cvv: form.cvv,
      });

      setSuccess(`Cartao salvo via endpoint ${result.endpoint}.`);
      onSaved(result);
      setForm(INITIAL_FORM);
      setTimeout(() => {
        onClose();
      }, 350);
    } catch (submissionError) {
      setError(
        submissionError instanceof Error
          ? submissionError.message
          : "Nao foi possivel salvar o cartao no momento.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="fixed inset-0 z-50 flex items-end justify-center bg-emerald-950/16 p-4 backdrop-blur-md md:items-center">
      <div className="flex w-full max-w-xl flex-col overflow-hidden rounded-[1.7rem] border border-emerald-200/70 bg-white shadow-[0_30px_90px_rgba(10,104,84,0.2)]">
        <header className="flex items-start justify-between gap-4 border-b border-emerald-100 bg-gradient-to-r from-emerald-50 via-white to-cyan-50/70 px-6 py-5 text-slate-900">
          <div>
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-emerald-700">
              Cartoes
            </p>
            <h2 className="mt-2 text-xl font-semibold">Cadastro de cartao</h2>
            <p className="mt-1 text-sm text-slate-500">
              Salve cartoes de credito ou debito para uso futuro.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-emerald-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-emerald-50"
          >
            Fechar
          </button>
        </header>

        <div className="space-y-4 px-6 py-5">
          <Field
            label="Nome do cartao (opcional)"
            placeholder="Ex.: Cartao principal"
            value={form.label}
            onChange={(value) => setForm((current) => ({ ...current, label: value }))}
            maxLength={30}
          />

          <Field
            label="Nome do titular (opcional)"
            placeholder="Ex.: Joao Silva"
            value={form.cardholderName}
            onChange={(value) =>
              setForm((current) => ({ ...current, cardholderName: value }))
            }
            maxLength={80}
          />

          <Field
            label="ID do Cliente"
            placeholder="Ex.: elias, cliente123"
            value={form.customerId}
            onChange={(value) =>
              setForm((current) => ({
                ...current,
                customerId: value,
              }))
            }
            maxLength={50}
          />

          <CardNumberField
            label="Numero do cartao"
            placeholder="0000 0000 0000 0000"
            value={form.cardNumber}
            onChange={(value) =>
              setForm((current) => ({
                ...current,
                cardNumber: formatCardNumber(value),
              }))
            }
            maxLength={23}
            detectedBrand={detectedBrand}
          />

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Field
              label="Validade"
              placeholder="MM/YY"
              value={form.expiry}
              onChange={(value) =>
                setForm((current) => ({
                  ...current,
                  expiry: formatExpiry(value),
                }))
              }
              maxLength={5}
              inputMode="numeric"
            />

            <Field
              label="CVV"
              placeholder="123"
              value={form.cvv}
              onChange={(value) =>
                setForm((current) => ({
                  ...current,
                  cvv: formatCvv(value),
                }))
              }
              maxLength={4}
              inputMode="numeric"
            />

          </div>

          <div className="min-h-6 text-sm">
            {error ? <p className="text-rose-600">{error}</p> : null}
            {success ? <p className="text-emerald-700">{success}</p> : null}
          </div>
        </div>

        <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-emerald-100 bg-white px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="rounded-full border border-emerald-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={() => {
              void submit();
            }}
            disabled={loading}
            className="rounded-full bg-[linear-gradient(135deg,#0089c7,#0068b4)] px-5 py-2 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(0,104,180,0.26)] transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Salvando..." : "Salvar cartao"}
          </button>
        </footer>
      </div>
    </section>
  );
}

type FieldProps = {
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  maxLength: number;
  inputMode?: "text" | "numeric";
};

function Field({
  label,
  placeholder,
  value,
  onChange,
  maxLength,
  inputMode = "text",
}: FieldProps) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.17em] text-emerald-800">
        {label}
      </span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        maxLength={maxLength}
        inputMode={inputMode}
        className="w-full rounded-xl border border-emerald-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
      />
    </label>
  );
}

function formatCardNumber(rawValue: string): string {
  const digitsOnly = rawValue.replace(/\D/g, "").slice(0, 19);
  return digitsOnly.replace(/(.{4})/g, "$1 ").trim();
}

function formatExpiry(rawValue: string): string {
  const digitsOnly = rawValue.replace(/\D/g, "").slice(0, 4);
  if (digitsOnly.length <= 2) {
    return digitsOnly;
  }

  return `${digitsOnly.slice(0, 2)}/${digitsOnly.slice(2)}`;
}

function formatCvv(rawValue: string): string {
  return rawValue.replace(/\D/g, "").slice(0, 4);
}

function detectCardBrand(digits: string): CardBrand | null {
  if (!digits) {
    return null;
  }

  for (const brand of CARD_BRANDS) {
    if (brand.isMatch(digits)) {
      return brand;
    }
  }

  return null;
}

type CardNumberFieldProps = {
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  maxLength: number;
  detectedBrand: CardBrand | null;
};

function CardNumberField({
  label,
  placeholder,
  value,
  onChange,
  maxLength,
  detectedBrand,
}: CardNumberFieldProps) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.17em] text-emerald-800">
        {label}
      </span>
      <div className="relative">
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          maxLength={maxLength}
          inputMode="numeric"
          className="w-full rounded-xl border border-emerald-200 bg-white px-3 py-2 pr-20 text-sm text-slate-900 outline-none transition focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
        />
        <span
          className={[
            "pointer-events-none absolute right-2 top-1/2 flex h-7 w-14 -translate-y-1/2 items-center justify-center rounded-md border transition",
            detectedBrand
              ? "border-cyan-200 bg-cyan-50"
              : "border-emerald-200 bg-emerald-50",
          ].join(" ")}
          aria-live="polite"
          title={detectedBrand ? detectedBrand.label : "Bandeira do cartao"}
        >
          <CardBrandIcon brandId={detectedBrand?.id} />
        </span>
      </div>
    </label>
  );
}

type CardBrandIconProps = {
  brandId?: string;
};

function CardBrandIcon({ brandId }: CardBrandIconProps) {
  switch (brandId) {
    case "visa":
      return <VisaIcon />;
    case "mastercard":
      return <MastercardIcon />;
    case "amex":
      return <AmexIcon />;
    case "elo":
      return <EloIcon />;
    case "hipercard":
      return <HipercardIcon />;
    case "discover":
      return <DiscoverIcon />;
    default:
      return <GenericCardIcon />;
  }
}

function GenericCardIcon() {
  return (
    <svg viewBox="0 0 56 24" className="h-5 w-12" aria-hidden="true">
      <rect x="2" y="3" width="52" height="18" rx="4" fill="#e5efe9" stroke="#b8d6cc" />
      <rect x="6" y="9" width="44" height="2.5" fill="#8aa8a0" />
      <rect x="8" y="14" width="10" height="3" rx="1" fill="#9ab7ae" />
    </svg>
  );
}

function VisaIcon() {
  return (
    <svg viewBox="0 0 56 24" className="h-5 w-12" aria-hidden="true">
      <rect x="1" y="1" width="54" height="22" rx="5" fill="#fff" stroke="#d3deea" />
      <text x="28" y="16" textAnchor="middle" fontSize="10" fontWeight="800" fill="#1a1f71" fontFamily="Arial, Helvetica, sans-serif">
        VISA
      </text>
    </svg>
  );
}

function MastercardIcon() {
  return (
    <svg viewBox="0 0 56 24" className="h-5 w-12" aria-hidden="true">
      <rect x="1" y="1" width="54" height="22" rx="5" fill="#fff" stroke="#e4e4e4" />
      <circle cx="24" cy="12" r="6.2" fill="#eb001b" />
      <circle cx="32" cy="12" r="6.2" fill="#f79e1b" fillOpacity="0.92" />
    </svg>
  );
}

function AmexIcon() {
  return (
    <svg viewBox="0 0 56 24" className="h-5 w-12" aria-hidden="true">
      <rect x="1" y="1" width="54" height="22" rx="5" fill="#2e77bc" stroke="#23649f" />
      <text x="28" y="15.5" textAnchor="middle" fontSize="7.8" fontWeight="800" fill="#ffffff" fontFamily="Arial, Helvetica, sans-serif">
        AMEX
      </text>
    </svg>
  );
}

function EloIcon() {
  return (
    <svg viewBox="0 0 56 24" className="h-5 w-12" aria-hidden="true">
      <rect x="1" y="1" width="54" height="22" rx="5" fill="#111" stroke="#222" />
      <circle cx="20" cy="12" r="5" fill="#f8cc00" />
      <circle cx="28" cy="12" r="5" fill="#00a1df" fillOpacity="0.9" />
      <circle cx="36" cy="12" r="5" fill="#ef3f23" fillOpacity="0.9" />
    </svg>
  );
}

function HipercardIcon() {
  return (
    <svg viewBox="0 0 56 24" className="h-5 w-12" aria-hidden="true">
      <rect x="1" y="1" width="54" height="22" rx="5" fill="#b3131b" stroke="#8c0f15" />
      <text x="28" y="15.5" textAnchor="middle" fontSize="6.6" fontWeight="700" fill="#ffffff" fontFamily="Arial, Helvetica, sans-serif">
        HIPERCARD
      </text>
    </svg>
  );
}

function DiscoverIcon() {
  return (
    <svg viewBox="0 0 56 24" className="h-5 w-12" aria-hidden="true">
      <rect x="1" y="1" width="54" height="22" rx="5" fill="#fff" stroke="#dfdfdf" />
      <text x="24" y="15" textAnchor="middle" fontSize="6.8" fontWeight="700" fill="#0f1e2e" fontFamily="Arial, Helvetica, sans-serif">
        DISC
      </text>
      <path d="M28 12c0-3.2 2.6-5.8 5.8-5.8h3.8v11.6h-3.8A5.8 5.8 0 0 1 28 12Z" fill="#f58220" />
    </svg>
  );
}
