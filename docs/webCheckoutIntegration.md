# Guia de Integração - Web Checkout para Agentes de IA

> Last updated by | Roberto Paulischen Carlos | 27 de mai. de 2026 at 10:35 BRT

Documentação técnica baseada nos repositórios `checkout-sandbox-store-portal`, `checkout-ms`, `checkout-bff` e `payments-gateway-ms`.

---

## 1. Autenticação - Gerar Token OAuth2

Antes de criar uma intenção de pagamento, é necessário obter um token de acesso via OAuth2 (`client_credentials`).

### Endpoint

```http
POST https://api.pre.globalgetnet.com/authentication/oauth2/access_token
```

### Exemplo cURL

```bash
curl --location --request POST 'https://api.pre.globalgetnet.com/authentication/oauth2/access_token' \
--header 'Content-Type: application/x-www-form-urlencoded' \
--header 'Accept: application/json' \
--data-urlencode 'grant_type=client_credentials' \
--data-urlencode 'client_id=cid_8ecdec75-0388-4e80-8053-b4859a4ff923' \
--data-urlencode 'client_secret=55c2f3c3-b339-4a2d-ad28-03676febdfd3'
```

### Resposta

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

O `access_token` retornado deve ser enviado no header `Authorization: Bearer {token}` em todas as chamadas subsequentes.

---

## 2. Como Criar Intenção de Pagamento para Agente

### Endpoint

```http
POST https://api.pre.globalgetnet.com/dpy/web-checkout/v1/payment-intent
```

### Headers

```http
Authorization: Bearer {access_token}
Content-Type: application/json
```

### 2.1 Payload - AI Agent (tokenização de cartão via agente de IA)

O fluxo `ai_agent` ativa a tokenização DPM com `verify_card: true` no `checkout-bff`, ignorando 3DS. Os campos `payment`, `product` e `shipping` **não devem ser enviados**.

```bash
curl --location --request POST 'https://api.pre.globalgetnet.com/dpy/web-checkout/v1/payment-intent' \
--header 'Authorization: Bearer {access_token}' \
--header 'Content-Type: application/json' \
--data-raw '{
  "order_id": "ORDER_CARD_VERIFY_12345",
  "customer": {
    "customer_id": "12345678912",
    "first_name": "Ana",
    "last_name": "Silva Costa",
    "name": "Ana Silva Costa",
    "email": "ana.silva@example.com.br",
    "document_type": "CPF",
    "document_number": "12345678912",
    "phone_number": "5511987654321",
    "billing_address": {
      "street": "Rua Augusta",
      "number": "2690",
      "complement": "Apto 82",
      "district": "Jardim Paulista",
      "city": "São Paulo",
      "state": "SP",
      "country": "BR",
      "postal_code": "01412100"
    }
  },
  "configurations": {
    "ai_agent": true
  }
}'
```

> **Nota:** O campo `ai_agent` é booleano. Quando `true`, o `checkout-bff` trata a intenção da mesma forma que `card_verification` para fins de tokenização (DPM) e bypass de 3DS. A diferença é que o campo `ai_agent` é persistido separadamente e pode ser consultado depois. Quando `false` ou ausente, o serializer do `checkout-ms` remove o campo da resposta.

### 2.2 Payload - Pagamento Padrão (com produtos)

```json
{
  "country": "AR",
  "checkout_type": "IFRAME",
  "order_id": "ORD1234567890",
  "customer": {
    "customer_id": "c129d793-d204-4610-8819-b8fb720a8552",
    "name": "John Doe",
    "first_name": "John",
    "last_name": "Doe",
    "email": "johndoe@emailtest.com",
    "checked_email": false,
    "document_type": "dni",
    "document_number": "37145386",
    "billing_address": {
      "street": "South Rockledge St",
      "number": "84",
      "country": "AR",
      "postal_code": "47230065",
      "district": "Back Bay",
      "city": "Boston",
      "state": "MA"
    },
    "phone_number": "5491112345678"
  },
  "payment": {
    "currency": "ARS",
    "amount": 10000000
  },
  "product": [
    {
      "product_type": "cash_carry",
      "title": "Look Fashion Leather Boot",
      "value": 5000000,
      "quantity": 1
    },
    {
      "product_type": "cash_carry",
      "title": "Look Fashion Blazer",
      "value": 5000000,
      "quantity": 1
    }
  ],
  "shipping": {
    "first_name": "John",
    "last_name": "Doe",
    "name": "John Doe",
    "phone_number": "5491112345678",
    "address": {
      "street": "South Rockledge St",
      "number": "84",
      "country": "AR",
      "postal_code": "47230065",
      "district": "Back Bay",
      "city": "Boston",
      "state": "MA"
    }
  }
}
```

> **IMPORTANTE:** O campo `amount` deve ser em **centavos** (menor unidade monetária). Ex: ARS 100.000,00 = `10000000`.

### 2.3 Payload - Card Verification (sem produtos/pagamento)

Quando o fluxo é de verificação de cartão, os campos `payment`, `product` e `shipping` são **proibidos** pela validação do `checkout-ms`:

```json
{
  "country": "AR",
  "checkout_type": "IFRAME",
  "order_id": "ORD1234567890",
  "customer": {
    "customer_id": "c129d793-d204-4610-8819-b8fb720a8552",
    "name": "John Doe",
    "first_name": "John",
    "last_name": "Doe",
    "email": "johndoe@emailtest.com",
    "checked_email": false,
    "document_type": "dni",
    "document_number": "37145386",
    "billing_address": {
      "street": "South Rockledge St",
      "number": "84",
      "country": "AR",
      "postal_code": "47230065",
      "district": "Back Bay",
      "city": "Boston",
      "state": "MA"
    },
    "phone_number": "5491112345678"
  },
  "configurations": {
    "card_verification": true
  }
}
```

### 2.4 Resposta da API

```json
{
  "payment_intent_id": "pi_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "trade_name": "Nome do Merchant",
  "redirect_url": "https://www.pre.globalgetnet.com/digital-checkout/web-checkout/hosted/pi_xxx...",
  "access_token": "eyJhbGciOi..."
}
```

| Campo | Descrição |
| --- | --- |
| `payment_intent_id` | Identificador único da intenção de pagamento |
| `trade_name` | Nome comercial do seller |
| `redirect_url` | URL para carregar o checkout (modo redirect ou iframe src) |
| `access_token` | Token de acesso para inicializar o `loader.js` |

### 2.5 Países e Moedas Suportados

| País | Código | Moedas | Tipo Documento | Nº Documento (teste) |
| --- | --- | --- | --- | --- |
| Argentina | AR | ARS | dni | 37145386 |
| Chile | CL | CLP | rut | 760864285 |
| México | MX | MXN, USD | rfc | XAXX010101000 |
| Colômbia | CO | COP | dni | 12345678 |
| Brasil | BR | BRL | cpf | 23447060034 |
| Espanha | ES | EUR | dni | 12345678 |
| Uruguai | UY | UYU, USD | dni | 50506468 |

---

## 3. Como Instanciar o Checkout num Agente (iframe)

### 3.1 Método 1: Via `loader.js` (recomendado para pagamento padrão com produtos)

O `loader.js` é o SDK oficial do Digital Checkout. Ele injeta o iframe do checkout dentro de um elemento DOM.

**Passo 1: Carregar o script do loader.js**

```ts
function addDigitalCheckoutScript(urlLoader: string): void {
  if (document.getElementById('digital-checkout')) return;

  const script = document.createElement('script');
  script.src = urlLoader;
  script.async = true;
  script.id = 'digital-checkout';
  document.body.appendChild(script);
}

// URL em UAT:
addDigitalCheckoutScript('https://www.pre.globalgetnet.com/digital-checkout/loader.js');
```

**Passo 2: Aguardar o loader estar disponível**

```ts
function waitForLoader(): Promise<void> {
  return new Promise((resolve) => {
    if (window.loader) return resolve();
    const interval = setInterval(() => {
      if (window.loader) {
        clearInterval(interval);
        resolve();
      }
    }, 100);
  });
}
```

**Passo 3: Inicializar o checkout**

```ts
declare global {
  interface Window {
    loader: {
      init: (config: {
        paymentIntentId: string;
        accessToken: string;
        checkoutType: string;   // 'iframe' | 'lightbox'
        elementId: string;      // ID do elemento DOM container
      }) => void;
    };
  }
}

// Após receber a resposta da API:
await waitForLoader();

window.loader.init({
  paymentIntentId: response.payment_intent_id,
  accessToken: response.access_token,
  checkoutType: 'iframe',
  elementId: 'checkout-container'
});
```

**Passo 4: Estrutura HTML no componente**

```html
<div id="checkout-container" style="min-height: 600px; width: 100%;"></div>
```

> **LIMITAÇÃO CONHECIDA:** O `loader.js` requer que o payment intent tenha `payment.amount` definido. Para intenções de `card_verification` ou `ai_agent` (que não possuem `payment`), o `loader.js` falha com:
> `TypeError: Cannot read properties of undefined (reading 'amount')`
> Nesses casos, use o Método 2 (iframe direto).

### 3.2 Método 2: Via iframe direto com `redirect_url` (card_verification / ai_agent)

Para fluxos sem `payment.amount`, carregue o checkout diretamente usando a `redirect_url` retornada pela API:

```tsx
function CheckoutIframe({ redirectUrl }: { redirectUrl: string }) {
  return (
    <iframe
      src={redirectUrl}
      style={{
        width: '100%',
        minHeight: '600px',
        border: 'none',
        borderRadius: '8px'
      }}
      title="Getnet Digital Checkout"
      allow="payment"
    />
  );
}
```

### 3.3 Dentro de um Chatbot (iframe embutido no chat)

Para renderizar o checkout dentro de uma janela de chat:

```tsx
function ChatCheckoutMessage({
  paymentIntentId,
  accessToken,
  redirectUrl,
  isAiAgent,
  isCardVerification
}: {
  paymentIntentId: string;
  accessToken: string;
  redirectUrl: string;
  isAiAgent?: boolean;
  isCardVerification?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const useDirectIframe = isAiAgent || isCardVerification;

  useEffect(() => {
    if (useDirectIframe || !containerRef.current || !window.loader) return;

    window.loader.init({
      paymentIntentId,
      accessToken,
      checkoutType: 'iframe',
      elementId: 'chat-checkout-container'
    });

    return () => {
      const iframe = containerRef.current?.querySelector('iframe');
      iframe?.remove();
    };
  }, [paymentIntentId, accessToken, useDirectIframe]);

  if (useDirectIframe) {
    return (
      <div style={{ width: '100%', maxWidth: '400px' }}>
        <iframe
          src={redirectUrl}
          style={{ width: '100%', minHeight: '500px', border: 'none', borderRadius: '8px' }}
          title="Checkout"
        />
      </div>
    );
  }

  return (
    <div
      id="chat-checkout-container"
      ref={containerRef}
      style={{ width: '100%', maxWidth: '400px', minHeight: '500px' }}
    />
  );
}
```

### 3.4 Comparação dos Métodos

| Aspecto | loader.js | iframe direto |
| --- | --- | --- |
| **Quando usar** | Pagamento padrão (com `payment.amount`) | `card_verification` / `ai_agent` |
| **Como funciona** | Injeta iframe via JS SDK | Carrega `redirect_url` diretamente |
| **Eventos `postMessage`** | Sim (enviados pelo loader) | Não (limitação conhecida) |
| **Parâmetros** | `paymentIntentId`, `accessToken`, `checkoutType`, `elementId` | Apenas `redirect_url` |

---

## 4. Como Capturar Eventos de Sucesso e Falha

### 4.1 Eventos via `postMessage` (modo loader.js)

Quando o checkout é carregado via `loader.js`, o Digital Checkout envia eventos via `window.postMessage`.

**Formatos de Evento Conhecidos**

O Digital Checkout pode enviar diferentes formatos de mensagem. Para capturar todos os cenários:

```ts
interface CheckoutEvent {
  type: 'success' | 'error' | 'close' | 'unknown';
  data?: Record<string, unknown>;
  raw: unknown;
}

function parseCheckoutEvent(event: MessageEvent): CheckoutEvent | null {
  const { data, origin } = event;

  if (!origin.includes('globalgetnet.com') && origin !== window.location.origin) {
    return null;
  }

  // Formato 1: String simples
  if (typeof data === 'string') {
    if (data === 'checkout-payment-success') {
      return { type: 'success', raw: data };
    }
    if (data === 'checkout-payment-error' || data === 'checkout-payment-denied') {
      return { type: 'error', raw: data };
    }
    if (data === 'remove-iframe') {
      return { type: 'close', raw: data };
    }
  }

  // Formato 2: Objeto com campo .event
  if (typeof data === 'object' && data !== null) {
    if ('event' in data) {
      const evt = (data as { event: string; data?: Record<string, unknown> });
      if (evt.event.includes('success')) {
        return { type: 'success', data: evt.data, raw: data };
      }
      if (evt.event.includes('error') || evt.event.includes('denied')) {
        return { type: 'error', data: evt.data, raw: data };
      }
    }

    // Formato 3: Objeto com campo .type
    if ('type' in data) {
      const typed = data as { type: string; data?: Record<string, unknown> };
      if (typed.type.includes('success')) {
        return { type: 'success', data: typed.data, raw: data };
      }
      if (typed.type.includes('error') || typed.type.includes('denied')) {
        return { type: 'error', data: typed.data, raw: data };
      }
    }

    // Formato 4: Objeto com campo .status
    if ('status' in data) {
      const statusData = data as { status: string; [key: string]: unknown };
      const successStatuses = ['APPROVED', 'PAID', 'COMPLETED', 'Authorized', 'Success'];
      if (successStatuses.includes(statusData.status)) {
        return { type: 'success', data: statusData as Record<string, unknown>, raw: data };
      }
      return { type: 'error', data: statusData as Record<string, unknown>, raw: data };
    }
  }

  return null;
}
```

**Exemplo Completo de Uso no Chatbot**

```ts
useEffect(() => {
  const handleMessage = (event: MessageEvent) => {
    const parsed = parseCheckoutEvent(event);
    if (!parsed) return;

    switch (parsed.type) {
      case 'success':
        console.log('Pagamento aprovado!', parsed.data);
        onPaymentSuccess(parsed);
        break;
      case 'error':
        console.log('Pagamento negado/erro', parsed.data);
        onPaymentError(parsed);
        break;
      case 'close':
        onCheckoutClosed();
        break;
    }
  };

  window.addEventListener('message', handleMessage);
  return () => window.removeEventListener('message', handleMessage);
}, []);
```

### 4.2 Limitação: `postMessage` não funciona no modo iframe direto

> **IMPORTANTE:** Quando o checkout é carregado via iframe direto (Método 2 - `redirect_url`), o Getnet **NÃO** envia `postMessage` para a janela pai. Esta é uma limitação conhecida.

**Alternativa: Consultar o Payment Intent para Obter o `card_id`**

Após o usuário completar o fluxo de `ai_agent` no iframe, consulte o payment intent para obter o `card_id`:

```bash
curl --location --request GET 'https://api.pre.globalgetnet.com/dpy/web-checkout/v1/payment-intent/{payment_intent_id}' \
--header 'Authorization: Bearer {access_token}'
```

A resposta conterá o `card_id` quando a tokenização for concluída com sucesso:

```json
{
  "payment_intent_id": "pi_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "configurations": {
    "ai_agent": true
  },
  "payment": {
    "method": "credit",
    "payment_method": {
      "card_id": "card_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    },
    "result": {
      "status": "Success"
    }
  }
}
```

O `card_id` é o identificador do cartão tokenizado e pode ser usado em pagamentos futuros sem que o comprador precise digitar os dados novamente. **Este é o dado principal a ser exibido no chat quando `ai_agent: true`.**

**Outras Alternativas**

1. **Polling da API:** Consultar periodicamente o `GET` do payment intent até que `payment.result.status` mude para `Success`.
2. **Webhook/Notificação:** O `checkout-ms` envia notificações via `notification-handler-ms` quando o status muda.
3. **`success_url`/`error_url`:** Configurar `success_url` e `error_url` nas `configurations` para redirecionar o iframe para uma página controlada pelo agente após o resultado.

---

## 5. Realizar Pagamento com o `card_id`

Após obter o `card_id` (via consulta do payment intent ou via `eventListener` de sucesso), é possível realizar um pagamento utilizando o cartão tokenizado.

### Endpoint

```http
POST https://api.pre.globalgetnet.com/dpm/payments-gwproxy/v2/payments/{card_id}
```

### Headers

```http
Authorization: Bearer {access_token}
Content-Type: application/json
```

### Exemplo cURL

```bash
curl --location -g --request POST 'https://api.pre.globalgetnet.com/dpm/payments-gwproxy/v2/payments/{card_id}' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer {access_token}' \
--data-raw '{
  "idempotency_key": "acbc7466-e718-408f-bebc-20962dbd3db5",
  "request_id": "6bf33588-f336-4259-aad7-51b9cfa21ba3",
  "order_id": "bc3126cd-aaaf-43aa-873c-d2deb5126ef1",
  "data": {
    "amount": 10000,
    "currency": "BRL",
    "customer_id": "0a88caaa-d41b-4fb2-8a0c-259ead7db61d",
    "payment": {
      "payment_method": "CREDIT",
      "transaction_type": "FULL",
      "number_installments": 1
    }
  }
}'
```

### Campos do Payload

| Campo | Descrição |
| --- | --- |
| `idempotency_key` | UUID único para garantir idempotência da requisição |
| `request_id` | UUID de rastreabilidade da requisição |
| `order_id` | Identificador do pedido |
| `data.amount` | Valor em centavos (ex: R$ 100,00 = `10000`) |
| `data.currency` | Moeda (ex: `BRL`, `ARS`, `MXN`) |
| `data.customer_id` | ID do cliente |
| `data.payment.payment_method` | Método de pagamento: `CREDIT` ou `DEBIT` |
| `data.payment.transaction_type` | Tipo de transação: `FULL` (à vista) |
| `data.payment.number_installments` | Número de parcelas (1 para à vista) |

---

## 6. Fluxo Completo - Resumo

```text
1. AUTENTICAR
   POST /authentication/oauth2/access_token
   -> Obtém access_token

2. CRIAR INTENÇÃO DE PAGAMENTO
   POST /dpy/web-checkout/v1/payment-intent
   Authorization: Bearer {access_token}
   Body: { customer, configurations: { ai_agent: true } }
   -> Obtém payment_intent_id + redirect_url

3. INSTANCIAR CHECKOUT
   - loader.js para pagamento padrão (com amount)
   - iframe direto para ai_agent/card_verification

4. CAPTURAR RESULTADO
   - postMessage (modo loader.js) OU
   - GET /dpy/web-checkout/v1/payment-intent/{payment_intent_id}
   -> Obtém card_id

5. REALIZAR PAGAMENTO
   POST /dpm/payments-gwproxy/v2/payments/{card_id}
   Authorization: Bearer {access_token}
   Body: { amount, currency, payment_method, ... }
   -> Pagamento processado
```

---

## 7. Referências de Código

| Arquivo | Repositório | Descrição |
| --- | --- | --- |
| `src/services/storeService.ts` | `checkout-sandbox-store-portal` | Service que chama `POST /payment-intent` |
| `src/services/interfaces.ts` | `checkout-sandbox-store-portal` | Interfaces `IPostIntentRequestData`, `IPostPaymentIntentRes` |
| `src/hooks/useCheckout.tsx` | `checkout-sandbox-store-portal` | Hook que monta o payload e chama o service |
| `src/pages/Checkout/CheckoutPage.tsx` | `checkout-sandbox-store-portal` | Página que inicializa `loader.js` e escuta `postMessage` |
| `src/utils/addDigitalCheckoutScript.ts` | `checkout-sandbox-store-portal` | Função que injeta o script do `loader.js` |
| `src/.../PaymentIntentSchema.js` | `checkout-ms` | Schema Joi de validação do payment intent |
| `src/.../PaymentIntentSerializer.js` | `checkout-ms` | Serializer que filtra `ai_agent` da resposta |
| `src/.../CheckoutPaymentBusiness.ts` | `checkout-bff` | Lógica de tokenização DPM e tratamento `ai_agent`/`card_verification` |
| `src/.../interfaces.ts` | `checkout-bff` | Interface `IGetPaymentIntentResponse` com `ai_agent` |

---

## 8. Configurações de Ambiente

**URLs (UAT / PRE)**

| Recurso | URL |
| --- | --- |
| Autenticação OAuth2 | `https://api.pre.globalgetnet.com/authentication/oauth2/access_token` |
| Payment Intent | `https://api.pre.globalgetnet.com/dpy/web-checkout/v1/payment-intent` |
| Pagamento (gwproxy) | `https://api.pre.globalgetnet.com/dpm/payments-gwproxy/v2/payments/{card_id}` |
| `loader.js` | `https://www.pre.globalgetnet.com/digital-checkout/loader.js` |
| Checkout Hosted | `https://www.pre.globalgetnet.com/digital-checkout/web-checkout/hosted/{payment_intent_id}` |
| Portal Sandbox | `https://www.pre.globalgetnet.com/sandbox-checkout-store/store` |
