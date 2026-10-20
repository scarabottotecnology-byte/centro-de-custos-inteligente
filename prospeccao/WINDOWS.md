# Sextante no seu computador Windows — custo zero

Tudo aqui é gratuito. O único gasto possível é um chip de celular para o
WhatsApp de prospecção, se você não tiver um número parado.

**O que o computador precisa:** Windows 10 ou 11 de 64 bits, 8 GB de RAM, 30 GB
livres no disco C: e virtualização ligada (vem ligada na maioria dos PCs; o
instalador do Docker avisa se não estiver).

**Ele precisa ficar ligado?** Só em horário comercial. O robô só envia de
segunda a sexta, das 9h às 17h30, e continua de onde parou quando o PC volta.

---

## Jeito rápido: dois cliques

1. Instale o **Docker Desktop** (item 1 abaixo) e, se for usar e-mail, crie o
   Gmail de prospecção (item 2).
2. Na pasta `prospeccao`, dê dois cliques em **`INICIAR.bat`**. Ele:
   - confere se o Docker está aberto (e abre, se não estiver);
   - na primeira vez, gera as senhas internas e pergunta o Gmail de prospecção
     (Enter para pular) e o **seu** WhatsApp, que recebe o aviso de lead;
   - liga os programas e abre o painel para conectar o WhatsApp do chip (item 5);
   - cria o atalho **Sextante** na área de trabalho.
3. Depois disso:
   - o atalho **Sextante** abre o painel no navegador: o que o robô está
     fazendo, o funil, os leads e as últimas mensagens. Se o Docker ou o robô
     estiverem parados, ele liga antes de abrir;
   - **`STATUS.bat`** mostra o mesmo em texto, com os registros do robô;
   - **`PARAR.bat`** pausa tudo;
   - o `INICIAR.bat` pode rodar de novo quando quiser: não pergunta nada outra vez.

O robô sempre começa em **simulação** (item 7). Os itens abaixo são o mesmo
processo feito à mão, se preferir ou se algo der errado.

---

## 1. Instalar os programas (uma vez)

1. **Docker Desktop** — https://www.docker.com/products/docker-desktop/
   Gratuito para uso pessoal e empresas com menos de 250 funcionários e menos
   de US$ 10 milhões de receita. Instale com as opções padrão (WSL 2) e
   reinicie o PC se ele pedir.
   Depois abra o Docker Desktop → ⚙️ **Settings → General** → marque
   **"Start Docker Desktop when you sign in to your computer"**.
2. **GitHub Desktop** — https://desktop.github.com/
   Entre com a sua conta do GitHub e clone o repositório
   `scarabottotecnology-byte/centro-de-custos-inteligente`
   (File → Clone repository). Ele fica em
   `Documentos\GitHub\centro-de-custos-inteligente`.
3. **Não deixar o PC dormir:** Configurações → Sistema → Energia (e bateria) →
   Tela e suspensão → "Quando conectado, suspender após": **Nunca**.

## 2. Criar a conta de e-mail de prospecção (grátis)

Pule se for usar só WhatsApp.

1. Crie um **Gmail novo**, só para prospecção. Não use o seu pessoal: se
   alguém marcar como spam, é essa conta que corre risco.
2. Ative a **verificação em duas etapas** nessa conta.
3. Abra https://myaccount.google.com/apppasswords, crie uma senha de app
   chamada "prospeccao" e copie os 16 caracteres (sem os espaços).

O Gmail grátis aceita até 500 destinatários por dia; o robô começa com 40.

## 3. Configurar

No Explorador de Arquivos, abra a pasta
`Documentos\GitHub\centro-de-custos-inteligente\prospeccao`, clique com o
botão direito num espaço vazio → **Abrir no Terminal**. Nesse terminal:

```powershell
Copy-Item .env.example .env
Copy-Item prospeccao.example.yaml prospeccao.yaml
[guid]::NewGuid().ToString('N')
[guid]::NewGuid().ToString('N')
[guid]::NewGuid().ToString('N')
notepad .env
```

Os três códigos que apareceram são as suas senhas internas. No Bloco de Notas:

- Cole um código em `POSTGRES_PASSWORD`, outro em `PROSPECTOR_API_TOKEN` e
  outro em `EVOLUTION_APIKEY`.
- Em `SMTP_USER`, `SMTP_FROM` e `IMAP_USER`, coloque o Gmail de prospecção.
- Em `SMTP_PASSWORD` e `IMAP_PASSWORD`, a senha de app de 16 letras.
- Salve e feche.

Depois:

```powershell
notepad prospeccao.yaml
```

O arquivo já vem configurado para a **Grande São Paulo**: os 39 municípios da
Região Metropolitana, agrupados por região (capital, ABC, oeste, sudoeste, norte
e leste). Para focar numa parte, apague as cidades que não quiser. Preencha
`aviso_dono_whatsapp` (o **seu** WhatsApp, que recebe o aviso de lead, no
formato `5511999998888`), confira `remetente` e leia os textos das mensagens.
Salve.

## 4. Ligar

No mesmo terminal:

```powershell
docker compose up -d --build
docker compose run --rm cli init
docker compose logs -f worker
```

A primeira subida leva uns 10 minutos (baixa os programas). Depois o robô
começa sozinho: baixa a base da Receita (~8 GB, pode levar 1 h) e carrega só as
empresas do seu ICP. Para sair dos logs: **Ctrl+C** — o robô continua rodando.

Ver o andamento a qualquer momento:

```powershell
docker compose run --rm cli funil
```

## 5. Conectar o WhatsApp do chip de prospecção

```powershell
docker compose run --rm cli whatsapp-conectar
```

Abra http://localhost:8081/manager no navegador. Entre com:
- **Server URL:** `http://localhost:8081`
- **API Key:** o `EVOLUTION_APIKEY` do seu `.env`

Na instância **prospeccao**, clique em **Conectar** e leia o QR code com o
celular do chip (WhatsApp → Aparelhos conectados → Conectar um aparelho).

## 6. Link de descadastro dos e-mails (opcional, grátis)

Pule se for usar só WhatsApp. Todo e-mail também diz "responda SAIR", e a
resposta já descadastra — o link é um segundo caminho.

1. Instale o **Tailscale** — https://tailscale.com/download/windows — e entre
   com uma conta (grátis).
2. Num terminal **como administrador**:
   ```powershell
   tailscale funnel --bg 8000
   ```
   Na primeira vez ele mostra um link para liberar o Funnel na sua conta;
   abra, aprove e rode o comando de novo. Ele responde com um endereço como
   `https://seu-pc.tail1234.ts.net`. Com `--bg`, volta sozinho depois de
   reiniciar o PC.
3. No `.env`, coloque esse endereço em `PROSPECTOR_PUBLIC_URL` e rode
   `docker compose up -d`.

## 7. Ensaiar e ligar o envio

O robô começa em **simulação**: faz tudo, menos enviar. Depois de um dia útil,
veja o que ele teria mandado:

```powershell
docker compose exec postgres psql -U prospector -c "select channel, body from outreach_messages where status = 'dry_run' limit 5"
```

Gostou dos textos? No `.env`, troque para `PROSPECTOR_DRY_RUN=false`, salve e:

```powershell
docker compose up -d
```

Daí em diante ele envia sozinho e te avisa no WhatsApp quando alguém responder
com interesse.

---

## Dia a dia

| Quero… | Comando (na pasta `prospeccao`) |
|---|---|
| ver se está tudo rodando | `docker compose ps` |
| ver o que ele está fazendo | `docker compose logs -f worker` |
| números do funil | `docker compose run --rm cli funil` |
| pausar o robô | `docker compose stop` |
| voltar a rodar | `docker compose start` |
| atualizar o código | GitHub Desktop → **Fetch origin / Pull**, depois `docker compose up -d --build` |

Depois que o Windows reinicia (atualização, queda de luz), o robô volta sozinho
quando você entra na sua conta e o Docker Desktop abre.

## Se der problema

- **"docker não é reconhecido"** — o Docker Desktop não está aberto. Abra e
  espere o ícone da baleia ficar parado.
- **WhatsApp desconectado** nos logs — repita o passo 5.
- **O download da Receita falha** — a Receita troca o endereço de tempos em
  tempos. O `.env` explica onde achar o token novo (`RECEITA_SHARE_TOKEN`).
- **Disco cheio** — o robô apaga sozinho o arquivo do mês anterior depois de
  carregar o novo. Se precisar liberar espaço já: Docker Desktop →
  Troubleshoot → Clean / Purge data apaga **tudo**, inclusive o banco; não use
  sem backup.
