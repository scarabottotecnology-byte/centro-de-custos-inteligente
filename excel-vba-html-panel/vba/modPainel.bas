Attribute VB_Name = "modPainel"
Option Explicit

' ============================================================
' Módulo padrão: gera os dados para o painel HTML e controla
' a atualização automática (Application.OnTime).
'
' Requer:
'   - Um UserForm chamado "frmPainelHTML" com um controle
'     "Microsoft Web Browser" chamado "WebBrowser1" (ver README).
'   - Uma planilha chamada "CentroDeCustos" com colunas:
'       A: Centro de Custo | B: Orçado | C: Realizado
'     a partir da linha 2 (linha 1 = cabeçalho).
'   - Uma pasta "painel" (com index.html) na mesma pasta do .xlsm.
' ============================================================

Private Const NOME_PLANILHA As String = "CentroDeCustos"
Private Const NOME_PASTA_PAINEL As String = "painel"
Private Const NOME_ARQUIVO_DADOS As String = "dados.js"
Private Const INTERVALO_SEGUNDOS As Long = 5

Private proximaExecucao As Date
Private atualizacaoAtiva As Boolean

' Abre (ou traz para frente) o painel HTML.
Public Sub AbrirPainelHTML()
    AtualizarDadosPainel

    If frmPainelHTML Is Nothing Then
        Load frmPainelHTML
    End If

    frmPainelHTML.Show vbModeless
End Sub

' Lê a planilha CentroDeCustos, grava painel/dados.js e,
' se o painel já estiver aberto, força o recarregamento.
Public Sub AtualizarDadosPainel()
    Dim ws As Worksheet
    Dim ultimaLinha As Long, i As Long
    Dim json As String
    Dim caminhoArquivo As String
    Dim nArq As Integer

    On Error Resume Next
    Set ws = ThisWorkbook.Sheets(NOME_PLANILHA)
    On Error GoTo 0

    If ws Is Nothing Then
        MsgBox "Não encontrei a planilha '" & NOME_PLANILHA & "'. Crie-a com as colunas" & _
               vbCrLf & "Centro de Custo | Orçado | Realizado a partir da linha 2.", vbExclamation
        Exit Sub
    End If

    ultimaLinha = ws.Cells(ws.Rows.Count, "A").End(xlUp).Row

    json = "["
    If ultimaLinha >= 2 Then
        For i = 2 To ultimaLinha
            If i > 2 Then json = json & ","
            json = json & "{""centro"":""" & EscaparJSON(CStr(ws.Cells(i, 1).Value)) & """," & _
                   """orcado"":" & ValorNumericoJSON(ws.Cells(i, 2).Value) & "," & _
                   """realizado"":" & ValorNumericoJSON(ws.Cells(i, 3).Value) & "}"
        Next i
    End If
    json = json & "]"

    caminhoArquivo = ThisWorkbook.Path & Application.PathSeparator & _
                      NOME_PASTA_PAINEL & Application.PathSeparator & NOME_ARQUIVO_DADOS

    nArq = FreeFile
    Open caminhoArquivo For Output As #nArq
    Print #nArq, "var dadosCentroCustos = " & json & ";"
    Print #nArq, "atualizarPainel(dadosCentroCustos);"
    Close #nArq

    On Error Resume Next
    frmPainelHTML.RecarregarPainel
    On Error GoTo 0
End Sub

' Liga a atualização automática a cada INTERVALO_SEGUNDOS segundos.
' Chamar em Workbook_Open.
Public Sub IniciarAtualizacaoAutomatica()
    atualizacaoAtiva = True
    AtualizarDadosPainel
    AgendarProximaExecucao
End Sub

' Desliga a atualização automática. Chamar em Workbook_BeforeClose.
Public Sub PararAtualizacaoAutomatica()
    atualizacaoAtiva = False
    On Error Resume Next
    Application.OnTime proximaExecucao, "modPainel.ExecutarAtualizacaoAgendada", , False
    On Error GoTo 0
End Sub

' Rotina chamada pelo Application.OnTime (precisa ser Public e sem argumentos).
Public Sub ExecutarAtualizacaoAgendada()
    If Not atualizacaoAtiva Then Exit Sub
    AtualizarDadosPainel
    AgendarProximaExecucao
End Sub

Private Sub AgendarProximaExecucao()
    proximaExecucao = Now + TimeSerial(0, 0, INTERVALO_SEGUNDOS)
    Application.OnTime proximaExecucao, "modPainel.ExecutarAtualizacaoAgendada"
End Sub

Private Function ValorNumericoJSON(ByVal v As Variant) As String
    If Len(Trim$(CStr(v))) = 0 Then
        ValorNumericoJSON = "0"
    Else
        ValorNumericoJSON = Replace(CStr(v), ",", ".")
    End If
End Function

Private Function EscaparJSON(ByVal texto As String) As String
    EscaparJSON = Replace(Replace(texto, "\", "\\"), """", "\""")
End Function
