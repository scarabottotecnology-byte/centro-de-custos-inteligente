# Protótipo: Painel HTML atualizado via macro VBA no Excel

Este protótipo mostra um painel HTML/CSS/JS customizado, aberto por uma macro
e atualizado automaticamente (a cada edição na planilha e a cada 5 segundos),
sem usar tabelas dinâmicas / gráficos nativos do Excel.

## Como funciona

- `painel/index.html` — o painel visual (tabela Orçado x Realizado por Centro de Custo).
- `painel/dados.js` — arquivo de dados que a macro reescreve a cada atualização.
  O `index.html` carrega esse arquivo e chama `atualizarPainel(dados)`.
- `vba/modPainel.bas` — módulo VBA: lê a planilha, gera `dados.js` e controla
  o timer de atualização automática (`Application.OnTime`).
- `vba/frmPainelHTML.txt` — código para o UserForm que hospeda o painel
  (usa o controle ActiveX "Microsoft Web Browser").
- `vba/ThisWorkbook.txt` — liga/desliga a atualização automática ao abrir/fechar o arquivo.
- `vba/Planilha_CentroDeCustos.txt` — atualiza o painel na hora quando a planilha é editada.

Você pode testar o painel isoladamente **sem Excel**: basta abrir
`painel/index.html` em qualquer navegador — ele já vem com dados de exemplo.

## Passo a passo no Excel

1. **Prepare a pasta.** Copie a pasta inteira `excel-vba-html-panel` (ou pelo
   menos a subpasta `painel`) para o mesmo diretório onde vai salvar seu `.xlsm`.
   Evite espaços e acentos no caminho da pasta, para não haver problema ao montar a URL `file:///`.

2. **Salve o arquivo como `.xlsm`** (Excel Macro-Enabled Workbook).

3. **Habilite a guia Desenvolvedor**, se ainda não estiver visível:
   Arquivo → Opções → Personalizar Faixa de Opções → marque "Desenvolvedor".

4. **Crie a planilha de dados.** Adicione (ou renomeie) uma planilha para
   `CentroDeCustos` com o cabeçalho na linha 1 e dados a partir da linha 2:

   | Centro de Custo | Orçado | Realizado |
   |---|---|---|
   | Administrativo | 50000 | 47500 |
   | Produção | 120000 | 131000 |
   | Comercial | 80000 | 76200 |

5. **Abra o Editor VBA** (Alt+F11).

6. **Importe o módulo padrão:** clique com o botão direito no projeto →
   Import File... → selecione `vba/modPainel.bas`.

7. **Crie o UserForm do painel:**
   - Inserir → UserForm.
   - Na janela Propriedades, mude `(Name)` para `frmPainelHTML`.
   - Na Caixa de Ferramentas, clique com o botão direito → Ferramentas Adicionais...
     e marque **"Microsoft Web Browser"**.
   - Arraste o novo ícone de globo para dentro do formulário e nomeie o
     controle (Propriedades → `(Name)`) como `WebBrowser1`. Redimensione o
     formulário como preferir (o código já reajusta o navegador ao redimensionar).
   - Dê duplo clique no formulário (fora do controle) para abrir o editor de
     código do formulário e cole todo o conteúdo de `vba/frmPainelHTML.txt`.

8. **Cole o código de `ThisWorkbook`:** no Project Explorer, duplo clique em
   `ThisWorkbook` e cole o conteúdo de `vba/ThisWorkbook.txt`.

9. **Cole o código da planilha:** duplo clique na planilha `CentroDeCustos`
   no Project Explorer e cole o conteúdo de `vba/Planilha_CentroDeCustos.txt`.

10. **Crie um botão para abrir o painel:** volte para o Excel, guia
    Desenvolvedor → Inserir → Botão (Controle de Formulário), desenhe na
    planilha, e atribua a macro `AbrirPainelHTML`.

11. **Salve, feche e reabra o arquivo** (para o `Workbook_Open` disparar),
    autorizando a execução de macros quando solicitado. Clique no botão
    para abrir o painel.

## Testando a atualização automática

- Edite qualquer valor nas colunas A:C da planilha `CentroDeCustos` — o
  painel atualiza na hora (via `Worksheet_Change`).
- Mesmo sem editar nada, o painel também se atualiza sozinho a cada 5
  segundos (via `Application.OnTime`) — útil se os dados vierem de uma
  consulta externa (Power Query, fórmulas com dados dinâmicos, etc.).
  Ajuste `INTERVALO_SEGUNDOS` em `modPainel.bas` conforme necessário.

## Observações e limitações

- O controle "Microsoft Web Browser" usa o motor legado do Internet
  Explorer (mshtml). Funciona bem para HTML/CSS/JS simples como este
  protótipo, mas não é o mesmo motor moderno do Edge — evite depender de
  recursos JS/CSS muito recentes.
- Na primeira execução, o Windows pode exibir um aviso de segurança sobre
  conteúdo ActiveX/bloqueado — permita a execução para o painel carregar.
- Se no futuro quiser trocar o motor legado por um baseado em Edge
  (WebView2) e ganhar atualização automática via eventos do próprio Excel
  (sem `Application.OnTime`), a alternativa é migrar para um **Office
  Add-in (Task Pane com Office.js)** — outra abordagem que também foi
  discutida, com prós/contras diferentes deste protótipo em VBA.
