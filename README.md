# ChatKit Starter com Checkout Conversacional

Este projeto é um starter de ChatKit com frontend em Vite + React e backend em FastAPI, já preparado para iniciar um fluxo de checkout dentro da própria conversa.

O comportamento principal é este:

1. O usuário conversa com o assistente.
2. Quando a mensagem indica intenção de checkout, o backend devolve um widget com alternativas de fluxo.
3. A escolha da ação dispara a criação da intenção de pagamento na Getnet.
4. O backend salva o último checkout no thread.
5. O frontend detecta o novo checkout e abre automaticamente um drawer com o iframe de pagamento.

## Visão geral

### Frontend

- Renderiza o ChatKit web component.
- Desabilita uploads para manter o exemplo focado no fluxo de chat e checkout.
- Consulta o backend para descobrir se existe um checkout recente.
- Abre o `CheckoutDrawer` automaticamente quando uma nova intenção é criada.

### Backend

- Expõe o endpoint `/chatkit` para o ChatKit web component.
- Detecta intenções de checkout em mensagens do usuário.
- Renderiza widgets de escolha, sucesso e erro dentro da conversa.
- Cria a intenção de pagamento na Getnet.
- Persiste o último checkout em memória para que o frontend consiga reabrir o fluxo.

### Checkout

- Suporta três fluxos: `payment`, `ai_agent` e `card_verification`.
- Gera o payload correto para a API da Getnet conforme o fluxo escolhido.
- Exibe o checkout em um iframe apontando para o `redirect_url` retornado pela API.

## Fluxo conversacional ponta a ponta

O fluxo implementado no código funciona assim:

1. O usuário envia uma mensagem como “quero pagar”, “checkout”, “tokenizar cartão” ou “verificar cartão”.
2. O backend identifica a intenção com base nas palavras-chave e no payload da mensagem.
3. Em vez de responder com texto simples, o backend envia um widget com três botões:
   - Checkout padrão
   - Tokenizar cartão
   - Verificar cartão
4. Cada botão dispara a action `checkout.launch` com um `checkoutRequest` já montado.
5. Ao receber a action, o backend valida o payload, obtém token OAuth2 na Getnet e cria a intenção de pagamento.
6. Se a criação der certo, o backend grava `latest_checkout` no metadata do thread com:
   - `payment_intent_id`
   - `redirect_url`
   - `flow`
   - `updated_at`
7. O frontend escuta o fim da resposta do ChatKit, consulta `/checkout/latest` e abre o `CheckoutDrawer` automaticamente quando identifica um checkout novo.
8. O `CheckoutDrawer` carrega o `redirect_url` em um iframe, sem tirar o usuário da conversa.

## Estrutura do projeto

```text
backend/
  app/
    main.py          # API FastAPI e proxy do ChatKit
    server.py        # lógica conversacional e action do checkout
    checkout.py      # modelos, widgets e cliente Getnet
    memory_store.py  # store em memória para threads e itens
frontend/
  src/
    App.tsx
    components/
      ChatKitPanel.tsx
      CheckoutDrawer.tsx
    lib/
      checkout.ts
      config.ts
docs/
  webCheckoutIntegration.md
```

## Requisitos

- Node.js com npm.
- Python 3.11 ou superior.
- Uma conta e credenciais válidas da OpenAI para o ChatKit.
- Credenciais válidas da Getnet para criar a intenção de checkout.

## Variáveis de ambiente

### Backend

- `OPENAI_API_KEY`: obrigatório para o ChatKit backend.
- `GETNET_CLIENT_ID`: obrigatório para autenticação OAuth2 na Getnet.
- `GETNET_CLIENT_SECRET`: obrigatório para autenticação OAuth2 na Getnet.
- `GETNET_AUTH_URL`: opcional, padrão `https://api.pre.globalgetnet.com/authentication/oauth2/access_token`.
- `GETNET_PAYMENT_INTENT_URL`: opcional, padrão `https://api.pre.globalgetnet.com/dpy/web-checkout/v1/payment-intent`.

O backend também tenta ler `GETNET_CLIENT_ID` e `GETNET_CLIENT_SECRET` de `backend/.env` se elas não estiverem presentes no ambiente.

### Frontend

- `VITE_CHATKIT_API_URL`: opcional, padrão `/chatkit`.
- `VITE_CHECKOUT_API_URL`: opcional, padrão `/checkout/intents`.
- `VITE_CHATKIT_API_DOMAIN_KEY`: opcional, padrão `domain_pk_localhost_dev`.

### Arquivo `.env.local`

Se preferir, você pode colocar `OPENAI_API_KEY` no `.env.local` na raiz do repositório. O script de backend tenta carregar esse arquivo automaticamente quando a variável não está exportada no shell.

## Início rápido

```bash
npm install
npm run dev
```

O que acontece quando o ambiente é compatível com o script padrão:

- o backend sobe em `127.0.0.1:8000`;
- o frontend sobe em `127.0.0.1:3000`;
- o frontend conversa com o backend via proxy em `/chatkit`.

## Execução no Windows

O comando `npm run dev` da raiz usa `backend/scripts/run.sh`, que é um script Bash. No Windows puro, esse caminho costuma falhar.

Para desenvolvimento local no Windows, use a execução manual:

```powershell
Set-Location "c:\South\Projetos\openai-chatkit-starter-app\chatkit\backend"
\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Em outro terminal:

```powershell
Set-Location "c:\South\Projetos\openai-chatkit-starter-app\chatkit\frontend"
node .\node_modules\vite\bin\vite.js --host 127.0.0.1 --port 3000
```

Se você estiver usando WSL, Git Bash ou outro shell compatível com Bash, o `npm run dev` da raiz pode funcionar normalmente.

## Como o checkout funciona no backend

O backend concentra a lógica do fluxo em `backend/app/server.py` e `backend/app/checkout.py`.

### Detecção de intenção

O assistente reconhece solicitações de checkout por palavras-chave como:

- checkout
- pagar
- pagamento
- tokenizar
- verificar

Quando uma mensagem do usuário bate com esse padrão, o backend retorna um widget de checkout em vez de seguir apenas com texto livre.

### Ação `checkout.launch`

Os botões do widget enviam uma action chamada `checkout.launch` com o payload `checkoutRequest` já montado.

Quando essa action chega ao backend:

1. o payload é validado com Pydantic;
2. o cliente Getnet obtém o access token OAuth2;
3. a API de payment intent é chamada;
4. o resultado é transformado em widget de sucesso;
5. o thread recebe `metadata.latest_checkout`.

### Persistência do último checkout

O repositório usa um store em memória. Isso significa que:

- o estado dura enquanto o processo está vivo;
- reiniciar o backend apaga threads e checkouts salvos;
- a solução é ideal para demo e desenvolvimento local.

## Fluxos de checkout suportados

### `payment`

Fluxo de pagamento padrão, com:

- `payment`
- `product`
- `shipping`

Esse fluxo exige os três blocos de dados porque representa uma compra completa.

### `ai_agent`

Fluxo pensado para tokenização assistida por agente de IA.

- envia `configurations.ai_agent = true`;
- não envia `payment`, `product` nem `shipping`;
- é útil quando a intenção é capturar ou preparar o cartão dentro do fluxo conversacional.

### `card_verification`

Fluxo de verificação de cartão.

- envia `configurations.card_verification = true`;
- não envia `payment`, `product` nem `shipping`;
- é o caminho mais enxuto para validar cartão dentro do checkout.

## Endpoints expostos

### `POST /chatkit`

Proxy do payload do web component do ChatKit para a implementação do servidor.

### `POST /checkout/intents`

Cria uma intenção de pagamento na Getnet a partir do payload do checkout.

### `GET /checkout/threads/{thread_id}/latest`

Retorna o último checkout salvo para um thread específico.

### `GET /checkout/latest`

Retorna o checkout mais recente conhecido em qualquer thread. Esse endpoint é usado pelo frontend para abrir automaticamente o drawer quando uma nova intenção é criada.

## Contratos principais

### Request de checkout

O tipo principal é `CheckoutIntentRequest`, definido no backend e espelhado no frontend.

Campos principais:

- `flow`: `payment`, `ai_agent` ou `card_verification`.
- `order_id`: identificador do pedido.
- `country`: padrão `BR`.
- `checkout_type`: padrão `IFRAME`.
- `customer`: dados do cliente e endereço de cobrança.
- `payment`: obrigatório no fluxo `payment`.
- `product`: obrigatório no fluxo `payment`.
- `shipping`: obrigatório no fluxo `payment`.
- `configurations`: usado pelos fluxos especiais.

### Response de checkout

O retorno consumido pelo frontend contém:

- `payment_intent_id`
- `trade_name`
- `redirect_url`
- `access_token`
- `flow`

O `access_token` pode estar ausente e o código já tolera isso.

## Como o frontend se comporta

O frontend em `frontend/src/components/ChatKitPanel.tsx` faz três coisas importantes:

1. monta o ChatKit com a URL e a domain key vindas de `frontend/src/lib/config.ts`;
2. desabilita uploads no composer;
3. usa `onResponseEnd` para buscar o último checkout e abrir o drawer quando necessário.

### `CheckoutDrawer`

O drawer em `frontend/src/components/CheckoutDrawer.tsx`:

- abre em sobreposição;
- mostra status e erros;
- renderiza o checkout em iframe quando existe `redirectUrl`;
- exibe um estado de espera enquanto o checkout ainda não foi criado.

### Helpers de checkout

O arquivo `frontend/src/lib/checkout.ts` centraliza:

- os tipos TypeScript do request e response;
- a criação de checkout via `POST /checkout/intents`;
- a leitura do checkout mais recente por thread;
- a leitura do checkout mais recente global.

## Exemplo de payload por fluxo

### Pagamento padrão

```json
{
  "flow": "payment",
  "order_id": "ORDER_123",
  "country": "BR",
  "checkout_type": "IFRAME",
  "customer": {
    "customer_id": "12345678912",
    "name": "Ana Silva Costa",
    "first_name": "Ana",
    "last_name": "Silva Costa",
    "email": "ana.silva@example.com.br",
    "checked_email": false,
    "document_type": "CPF",
    "document_number": "12345678912",
    "phone_number": "5511987654321",
    "billing_address": {
      "street": "Rua Augusta",
      "number": "2690",
      "country": "BR",
      "postal_code": "01412100",
      "district": "Jardim Paulista",
      "city": "São Paulo",
      "state": "SP"
    }
  },
  "payment": {
    "currency": "BRL",
    "amount": 10000
  },
  "product": [
    {
      "product_type": "cash_carry",
      "title": "Plano Starter",
      "value": 10000,
      "quantity": 1
    }
  ],
  "shipping": {
    "first_name": "Ana",
    "last_name": "Silva Costa",
    "name": "Ana Silva Costa",
    "phone_number": "5511987654321",
    "address": {
      "street": "Rua Augusta",
      "number": "2690",
      "country": "BR",
      "postal_code": "01412100",
      "district": "Jardim Paulista",
      "city": "São Paulo",
      "state": "SP"
    }
  }
}
```

### Tokenização assistida por agente

```json
{
  "flow": "ai_agent",
  "order_id": "ORDER_123",
  "country": "BR",
  "checkout_type": "IFRAME",
  "customer": {
    "customer_id": "12345678912",
    "name": "Ana Silva Costa",
    "first_name": "Ana",
    "last_name": "Silva Costa",
    "email": "ana.silva@example.com.br",
    "checked_email": false,
    "document_type": "CPF",
    "document_number": "12345678912",
    "phone_number": "5511987654321",
    "billing_address": {
      "street": "Rua Augusta",
      "number": "2690",
      "country": "BR",
      "postal_code": "01412100",
      "district": "Jardim Paulista",
      "city": "São Paulo",
      "state": "SP"
    }
  },
  "configurations": {
    "ai_agent": true
  }
}
```

### Verificação de cartão

```json
{
  "flow": "card_verification",
  "order_id": "ORDER_123",
  "country": "BR",
  "checkout_type": "IFRAME",
  "customer": {
    "customer_id": "12345678912",
    "name": "Ana Silva Costa",
    "first_name": "Ana",
    "last_name": "Silva Costa",
    "email": "ana.silva@example.com.br",
    "checked_email": false,
    "document_type": "CPF",
    "document_number": "12345678912",
    "phone_number": "5511987654321",
    "billing_address": {
      "street": "Rua Augusta",
      "number": "2690",
      "country": "BR",
      "postal_code": "01412100",
      "district": "Jardim Paulista",
      "city": "São Paulo",
      "state": "SP"
    }
  },
  "configurations": {
    "card_verification": true
  }
}
```

## Saídas do backend

Quando o checkout é criado com sucesso, o backend responde na conversa com um widget de sucesso contendo:

- o flow usado;
- o payment intent criado;
- um link para abrir o checkout manualmente.

Se houver erro, o backend devolve um widget de falha com a mensagem da exceção e orientação para revisar as credenciais da Getnet.

## Limitações atuais

- O store é em memória, então threads e checkouts se perdem ao reiniciar o backend.
- O exemplo foi feito para desenvolvimento e demonstração, não para produção sem persistência.
- O fluxo depende de credenciais reais da Getnet para criar intenções válidas.
- O comando de execução automática da raiz usa Bash, então o caminho padrão não é o melhor no Windows puro.

## Personalização

Se quiser adaptar o starter, os pontos de entrada são:

- `frontend/src/lib/config.ts` para URLs e domain key.
- `frontend/src/components/ChatKitPanel.tsx` para comportamento de abertura do checkout.
- `frontend/src/components/CheckoutDrawer.tsx` para a apresentação do iframe.
- `backend/app/server.py` para a lógica de conversa e action do checkout.
- `backend/app/checkout.py` para payloads, validações e widgets.
- `backend/app/memory_store.py` para trocar a store em memória por persistência real.

## Referências úteis

- Guia técnico do Web Checkout: [docs/webCheckoutIntegration.md](docs/webCheckoutIntegration.md)
- Script de backend: [backend/scripts/run.sh](backend/scripts/run.sh)
