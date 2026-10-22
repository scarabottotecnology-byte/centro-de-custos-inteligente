# Sextante num servidor na internet — Oracle Cloud grátis

O robô fica ligado 24 horas num servidor da Oracle, de graça, e você acompanha
pelo painel de qualquer lugar, inclusive pelo celular. Não precisa deixar o PC
ligado.

**O que a Oracle dá de graça, para sempre:** um servidor ARM com até 4
processadores, 24 GB de memória e 200 GB de disco. O robô usa bem menos que
isso.

**O que você precisa:** um e-mail, um cartão de crédito (só para verificação:
a conta grátis não cobra nada) e uns 30 minutos.

---

## 1. Criar a conta

1. Abra https://www.oracle.com/br/cloud/free/ e clique em **Comece
   gratuitamente**.
2. Na **região inicial** (*Home Region*), escolha **Brazil East (Sao Paulo)**.
   Ela não muda depois.
3. Termine o cadastro. A aprovação pode levar alguns minutos.

## 2. Criar o servidor

No painel da Oracle: menu **☰** → **Compute** → **Instances** →
**Create instance**.

| Campo | O que colocar |
|---|---|
| **Name** | `sextante` |
| **Image** | **Change image** → **Canonical Ubuntu** 24.04 |
| **Shape** | **Change shape** → **Ampere** → `VM.Standard.A1.Flex`, **4 OCPUs** e **24 GB** |
| **Networking** | deixe criar uma rede nova, com **Assign a public IPv4 address** ligado |
| **Add SSH keys** | **Save private key** e guarde o arquivo (só para manutenção) |
| **Boot volume** | **Specify a custom boot volume size**: `100` GB |

Ainda nessa tela, abra **Show advanced options** → aba **Management** →
**Paste cloud-init script** e cole o bloco abaixo, **trocando o seu WhatsApp e
a senha**:

```bash
#!/bin/bash
export WHATSAPP="11999998888"
export SENHA="troque-por-uma-senha-forte"
curl -fsSL https://raw.githubusercontent.com/scarabottotecnology-byte/centro-de-custos-inteligente/main/prospeccao/servidor/instalar.sh | bash
```

- **WHATSAPP** é o **seu** número, com DDD. Ele recebe o aviso quando um lead
  responder.
- **SENHA** é a senha do painel: 10 ou mais caracteres, só letras, números e
  `. _ @ ! -`.

Clique em **Create**. Se aparecer **Out of capacity**, tente outro
*Availability domain*, ou 2 OCPUs e 12 GB, ou de novo mais tarde: é falta de
vaga momentânea na Oracle.

## 3. Abrir as portas do painel

A Oracle bloqueia tudo por padrão. Na página do servidor:
**Primary VNIC** → clique na **Subnet** → **Security Lists** →
**Default Security List** → **Add Ingress Rules**:

| Campo | Valor |
|---|---|
| Source CIDR | `0.0.0.0/0` |
| IP Protocol | TCP |
| Destination Port Range | `80,443` |

## 4. Entrar no painel

Na página do servidor, copie o **Public IP address** (por exemplo
`129.151.10.20`). Espere uns **15 minutos** depois de criar o servidor e abra:

```
https://129.151.10.20.sslip.io
```

Troque pelo seu IP. Entre com a senha que você escolheu. Se a página ainda não
abrir, espere mais 5 minutos: na primeira vez ele baixa e monta os programas.

## 5. Conectar o WhatsApp do chip

No painel, em **WhatsApp do chip**, clique em **Conectar** e leia o QR code
com o celular do chip de prospecção (**WhatsApp** → **Aparelhos conectados** →
**Conectar um aparelho**).

Pronto. O robô começa em **simulação**: faz tudo, menos enviar. Depois de um
dia útil, veja no painel o que ele teria mandado.

---

## Manutenção (precisa da chave SSH)

No Windows, abra o **Terminal** na pasta onde salvou a chave e entre no
servidor (troque o nome do arquivo e o IP):

```powershell
ssh -i .\ssh-key-2026-10-22.key ubuntu@129.151.10.20
```

| Quero… | Comando, dentro do servidor |
|---|---|
| ligar o envio de verdade | `sudo sed -i 's/^PROSPECTOR_DRY_RUN=.*/PROSPECTOR_DRY_RUN=false/' /opt/sextante/prospeccao/.env` e depois o de atualizar |
| atualizar o robô | `curl -fsSL https://raw.githubusercontent.com/scarabottotecnology-byte/centro-de-custos-inteligente/main/prospeccao/servidor/instalar.sh \| sudo bash` |
| ver o que ele está fazendo | `cd /opt/sextante/prospeccao && sudo docker compose logs -f worker` |
| ver o registro da instalação | `sudo cat /var/log/sextante-instalar.log` |

A configuração fica em `/opt/sextante/prospeccao/.env` e `prospeccao.yaml`;
atualizar não mexe nelas.

## Bom saber

- **A Oracle pode desligar servidores grátis ociosos.** Se o uso ficar muito
  baixo por 7 dias seguidos, ela recupera a máquina. Para evitar, passe a conta
  para **Pay As You Go** (menu da conta → *Upgrade*): continua sem custo dentro
  dos limites grátis, e a máquina deixa de ser recuperada.
- **O endereço `sslip.io`** funciona sem comprar domínio. Se um dia quiser um
  endereço próprio, como `prospeccao.keystone.com.br`, aponte o domínio para o
  IP, troque `PROSPECTOR_SITE` e `PROSPECTOR_PUBLIC_URL` no `.env` e atualize.
- **O que fica exposto na internet:** só o painel (protegido pela senha), o
  link de descadastro dos e-mails e a checagem de saúde. O resto fica na rede
  interna do servidor.
