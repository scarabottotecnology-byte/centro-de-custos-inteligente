# LinkedIn: empresários e C-level para a prospecção

Dois scripts que transformam o LinkedIn numa planilha de decisores (sócios,
fundadores, donos, CEO, CFO, diretoria), prontos para receber a apresentação da
Keystone por e-mail. Rodam no seu computador: o LinkedIn não abre na nuvem.

| Script | De onde vem | Risco para a conta |
|---|---|---|
| `filtrar_conexoes.py` | A exportação oficial das suas conexões | Nenhum: só lê um arquivo |
| `coletar.py` | Perfis abertos um a um com a sua sessão ([joeyism/linkedin_scraper](https://github.com/joeyism/linkedin_scraper) v3) | Existe: o LinkedIn restringe contas que leem perfis em massa |

Comece sempre pelo `filtrar_conexoes.py`. Use o `coletar.py` só para os
perfis que ficaram sem e-mail ou para links que você juntou numa busca.

## 1. Exportar as conexões (grátis, sem risco)

1. No LinkedIn: **Eu → Configurações → Privacidade de dados → Obter uma cópia dos seus dados**.
2. Marque só **Conexões** e peça o arquivo. Ele chega por e-mail em alguns minutos.
3. Descompacte e copie o `Connections.csv` para esta pasta.

```
python filtrar_conexoes.py Connections.csv
```

Sai `saida/decisores_conexoes.csv` com nome, cargo, empresa, tipo de decisor
e e-mail (quando a pessoa deixa visível para conexões). Os links de quem ficou
sem e-mail vão para `perfis.txt`.

## 2. Ler perfis (opcional)

Instalação, uma vez (Python 3.10 ou mais novo):

```
pip install -r requirements.txt
playwright install chromium
python criar_sessao.py
```

O `criar_sessao.py` abre o navegador para você entrar no LinkedIn e guarda a
sessão em `sessao_linkedin.json`. A senha não fica salva em lugar nenhum.

Depois:

```
python coletar.py
```

Ele lê `perfis.txt` (um link por linha), abre cada perfil com uma pausa de 20 a
45 segundos e grava `saida/perfis_linkedin.csv`. São no máximo 40 perfis por
execução; rodar de novo continua de onde parou. Se o LinkedIn limitar ou pedir
login, o script para e guarda o que já tinha: espere algumas horas.

**Não aumente as pausas nem o limite.** Ler perfis em massa viola os termos de
uso do LinkedIn e a conta usada pode ser restringida. É a sua conta pessoal.

## 3. Do CSV ao e-mail

- Quem já tem e-mail: entra na HubSpot e recebe o rascunho com o modelo de
  `comercial/email/apresentacao.html`.
- Quem não tem: o Apollo (plano gratuito) encontra o e-mail profissional a
  partir de nome e empresa, a 1 crédito por pessoa.

Cuidados (LGPD): fale só sobre assunto profissional, use o e-mail de trabalho
quando houver e mantenha o descadastro no rodapé, como no modelo.

## Arquivos que ficam só no seu computador

`sessao_linkedin.json` (dá acesso à sua conta), `Connections.csv`, `perfis.txt`
e `saida/` (dados de contatos) estão no `.gitignore`. Não suba para o GitHub.
