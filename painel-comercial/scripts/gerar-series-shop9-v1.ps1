# ============================================================
# ARILUB - SERIE TEMPORAL COMERCIAL SHOP9
# V1.1
#
# Fonte:
# C:\ARILUB\Comercial\integrador-v2\saida\shop9-v2.json
#
# Saida:
# C:\ARILUB\Comercial\integrador-v2\saida\shop9-series-v1.json
#
# Objetivo:
# Gerar series agregadas por dia e por mes para o Painel Comercial.
# Nao acessa SQL. Nao altera Shop9. Trabalha somente sobre o JSON
# homologado produzido pelo extrator Shop9 V2/V1.4 reconstruido.
# ============================================================

$ErrorActionPreference = "Stop"

$ArquivoEntrada = "C:\ARILUB\Comercial\integrador-v2\saida\shop9-v2.json"
$ArquivoSaida   = "C:\ARILUB\Comercial\integrador-v2\saida\shop9-series-v1.json"

function Decimal-Zero {
    param($Valor)

    if ($null -eq $Valor -or $Valor -is [System.DBNull]) {
        return [decimal]0
    }

    try {
        return [decimal]$Valor
    }
    catch {
        return [decimal]0
    }
}

function Inteiro-Zero {
    param($Valor)

    if ($null -eq $Valor -or $Valor -is [System.DBNull]) {
        return [int64]0
    }

    try {
        return [int64]$Valor
    }
    catch {
        return [int64]0
    }
}

function Data-Valida {
    param($Valor)

    if ($null -eq $Valor) {
        return $false
    }

    $texto = ([string]$Valor).Trim()

    return ($texto -match '^\d{4}-\d{2}-\d{2}$')
}

function Nova-LinhaDia {
    param([string]$Data)

    return [ordered]@{
        data = $Data

        orcEmitidosQtd = 0
        orcEmitidosValor = [decimal]0

        orcConvertidosQtd = 0
        orcConvertidosValor = [decimal]0

        vendasQtd = 0
        vendasValor = [decimal]0
    }
}

function Arredondar-Moeda {
    param($Valor)

    return [math]::Round(
        [decimal]$Valor,
        2,
        [MidpointRounding]::AwayFromZero
    )
}

Write-Host ""
Write-Host "==============================================="
Write-Host " ARILUB - SERIE TEMPORAL SHOP9 V1.1"
Write-Host "==============================================="
Write-Host ""

if (-not (Test-Path $ArquivoEntrada)) {
    throw "Arquivo de entrada nao encontrado: $ArquivoEntrada"
}

Write-Host "Carregando shop9-v2.json..."

$dados = Get-Content -Raw -Encoding UTF8 $ArquivoEntrada | ConvertFrom-Json

if ($null -eq $dados.orcamentos) {
    throw "Estrutura invalida: bloco 'orcamentos' nao encontrado."
}

if ($null -eq $dados.vendasSemOrc) {
    throw "Estrutura invalida: bloco 'vendasSemOrc' nao encontrado."
}

$dias = @{}

$orcTotalCalculado = 0
$orcSemDataQtd = 0
$orcSemDataValor = [decimal]0

$vendasViaOrcQtd = 0
$vendasViaOrcValor = [decimal]0
$vendasViaOrcSemDataQtd = 0
$vendasViaOrcSemDataValor = [decimal]0

$vendasSemOrcQtd = 0
$vendasSemOrcValor = [decimal]0
$vendasSemOrcSemDataQtd = 0
$vendasSemOrcSemDataValor = [decimal]0

Write-Host "Agregando ORCs..."

foreach ($orc in @($dados.orcamentos)) {

    $orcTotalCalculado++
    $valorOrcado = Decimal-Zero $orc.valorOrcado

    if (Data-Valida $orc.dataOrc) {

        $chave = ([string]$orc.dataOrc).Trim()

        if (-not $dias.ContainsKey($chave)) {
            $dias[$chave] = Nova-LinhaDia $chave
        }

        $dias[$chave].orcEmitidosQtd++
        $dias[$chave].orcEmitidosValor += $valorOrcado
    }
    else {
        $orcSemDataQtd++
        $orcSemDataValor += $valorOrcado
    }

    if ($null -ne $orc.vendaOrdem) {

        $vendasViaOrcQtd++
        $valorVendido = Decimal-Zero $orc.valorVendido
        $vendasViaOrcValor += $valorVendido

        if (Data-Valida $orc.dataVenda) {

            $chaveVenda = ([string]$orc.dataVenda).Trim()

            if (-not $dias.ContainsKey($chaveVenda)) {
                $dias[$chaveVenda] = Nova-LinhaDia $chaveVenda
            }

            $dias[$chaveVenda].orcConvertidosQtd++
            $dias[$chaveVenda].orcConvertidosValor += $valorVendido

            $dias[$chaveVenda].vendasQtd++
            $dias[$chaveVenda].vendasValor += $valorVendido
        }
        else {
            $vendasViaOrcSemDataQtd++
            $vendasViaOrcSemDataValor += $valorVendido
        }
    }
}

Write-Host "Agregando VND sem ORC..."

foreach ($venda in @($dados.vendasSemOrc)) {

    $vendasSemOrcQtd++
    $valorVendido = Decimal-Zero $venda.valorVendido
    $vendasSemOrcValor += $valorVendido

    if (Data-Valida $venda.dataVenda) {

        $chaveVenda = ([string]$venda.dataVenda).Trim()

        if (-not $dias.ContainsKey($chaveVenda)) {
            $dias[$chaveVenda] = Nova-LinhaDia $chaveVenda
        }

        $dias[$chaveVenda].vendasQtd++
        $dias[$chaveVenda].vendasValor += $valorVendido
    }
    else {
        $vendasSemOrcSemDataQtd++
        $vendasSemOrcSemDataValor += $valorVendido
    }
}

Write-Host "Montando serie diaria..."

$diasOrdenados = @(
    $dias.Keys |
    Sort-Object |
    ForEach-Object {

        $linha = $dias[$_]

        [PSCustomObject][ordered]@{
            data = $linha.data

            orcEmitidosQtd =
                [int64]$linha.orcEmitidosQtd

            orcEmitidosValor =
                Arredondar-Moeda $linha.orcEmitidosValor

            orcConvertidosQtd =
                [int64]$linha.orcConvertidosQtd

            orcConvertidosValor =
                Arredondar-Moeda $linha.orcConvertidosValor

            vendasQtd =
                [int64]$linha.vendasQtd

            vendasValor =
                Arredondar-Moeda $linha.vendasValor

            ticketMedio = if (
                [int64]$linha.vendasQtd -gt 0
            ) {
                Arredondar-Moeda (
                    [decimal]$linha.vendasValor /
                    [decimal]$linha.vendasQtd
                )
            }
            else {
                [decimal]0
            }
        }
    }
)

Write-Host "Montando serie mensal..."

$mesesHash = @{}

foreach ($dia in $diasOrdenados) {

    $mes = $dia.data.Substring(0, 7)

    if (-not $mesesHash.ContainsKey($mes)) {

        $mesesHash[$mes] = [ordered]@{
            mes = $mes

            orcEmitidosQtd = 0
            orcEmitidosValor = [decimal]0

            orcConvertidosQtd = 0
            orcConvertidosValor = [decimal]0

            vendasQtd = 0
            vendasValor = [decimal]0
        }
    }

    $mesesHash[$mes].orcEmitidosQtd +=
        [int64]$dia.orcEmitidosQtd

    $mesesHash[$mes].orcEmitidosValor +=
        [decimal]$dia.orcEmitidosValor

    $mesesHash[$mes].orcConvertidosQtd +=
        [int64]$dia.orcConvertidosQtd

    $mesesHash[$mes].orcConvertidosValor +=
        [decimal]$dia.orcConvertidosValor

    $mesesHash[$mes].vendasQtd +=
        [int64]$dia.vendasQtd

    $mesesHash[$mes].vendasValor +=
        [decimal]$dia.vendasValor
}

$mesesOrdenados = @(
    $mesesHash.Keys |
    Sort-Object |
    ForEach-Object {

        $linha = $mesesHash[$_]

        [PSCustomObject][ordered]@{
            mes = $linha.mes

            orcEmitidosQtd =
                [int64]$linha.orcEmitidosQtd

            orcEmitidosValor =
                Arredondar-Moeda $linha.orcEmitidosValor

            orcConvertidosQtd =
                [int64]$linha.orcConvertidosQtd

            orcConvertidosValor =
                Arredondar-Moeda $linha.orcConvertidosValor

            vendasQtd =
                [int64]$linha.vendasQtd

            vendasValor =
                Arredondar-Moeda $linha.vendasValor

            ticketMedio = if (
                [int64]$linha.vendasQtd -gt 0
            ) {
                Arredondar-Moeda (
                    [decimal]$linha.vendasValor /
                    [decimal]$linha.vendasQtd
                )
            }
            else {
                [decimal]0
            }
        }
    }
)

$fonteOrcTotal = 0
$fonteOrcValor = [decimal]0
$fonteVendasTotal = 0
$fonteVendasValor = [decimal]0

if ($null -ne $dados.resumo.orcamentos) {
    $fonteOrcTotal =
        Inteiro-Zero $dados.resumo.orcamentos.total

    $fonteOrcValor =
        Decimal-Zero $dados.resumo.orcamentos.valorOrcadoTotal
}

if ($null -ne $dados.resumo.vendas) {
    $fonteVendasTotal =
        Inteiro-Zero $dados.resumo.vendas.total

    $fonteVendasValor =
        Decimal-Zero $dados.resumo.vendas.valorTotal
}

$vendasTotalCalculado =
    [int64]$vendasViaOrcQtd +
    [int64]$vendasSemOrcQtd

$vendasValorCalculado =
    Arredondar-Moeda (
        [decimal]$vendasViaOrcValor +
        [decimal]$vendasSemOrcValor
    )

$orcValorCalculado =
    Arredondar-Moeda (
        (
            @($dados.orcamentos) |
            ForEach-Object {
                Decimal-Zero $_.valorOrcado
            } |
            Measure-Object -Sum
        ).Sum
    )

$orcQtdSerie =
    [int64](
        (
            $diasOrdenados |
            Measure-Object -Property orcEmitidosQtd -Sum
        ).Sum
    )

$vendasQtdSerie =
    [int64](
        (
            $diasOrdenados |
            Measure-Object -Property vendasQtd -Sum
        ).Sum
    )

$orcValorSerie =
    Arredondar-Moeda (
        (
            $diasOrdenados |
            Measure-Object -Property orcEmitidosValor -Sum
        ).Sum
    )

$vendasValorSerie =
    Arredondar-Moeda (
        (
            $diasOrdenados |
            Measure-Object -Property vendasValor -Sum
        ).Sum
    )

$datasDisponiveis = @(
    $diasOrdenados |
    Select-Object -ExpandProperty data
)

$dataInicial = $null
$dataFinal = $null

if ($datasDisponiveis.Count -gt 0) {
    $dataInicial = $datasDisponiveis[0]
    $dataFinal = $datasDisponiveis[
        $datasDisponiveis.Count - 1
    ]
}

$documento = [ordered]@{

    meta = [ordered]@{
        sistema =
            "ARILUB Comercial"

        versao =
            "series-shop9-1.1.0"

        geradoEm =
            (Get-Date).ToString(
                "yyyy-MM-ddTHH:mm:ss"
            )

        fonte =
            "shop9-v2.json"

        fonteExtratorVersao =
            $dados.meta.versaoExtrator

        somenteLeitura =
            $true

        regraVenda =
            "VND via ORC + VND sem ORC; cada VND contada uma unica vez"

        observacaoConversao =
            "orcConvertidosQtd e orcConvertidosValor usam a data da VND. Nao interpretar a razao mensal entre ORCs emitidos e ORCs convertidos como taxa de conversao de coorte."
    }

    cobertura = [ordered]@{
        dataInicial = $dataInicial
        dataFinal = $dataFinal
        diasComMovimento = $diasOrdenados.Count
        mesesComMovimento = $mesesOrdenados.Count
    }

    auditoria = [ordered]@{

        orcamentos = [ordered]@{
            fonteTotal = $fonteOrcTotal
            calculadoTotal = $orcTotalCalculado
            serieComData = $orcQtdSerie
            semData = $orcSemDataQtd

            fonteValor =
                Arredondar-Moeda $fonteOrcValor

            calculadoValor =
                $orcValorCalculado

            serieValorComData =
                $orcValorSerie

            semDataValor =
                Arredondar-Moeda $orcSemDataValor

            quantidadeOk =
                (
                    [int64]$fonteOrcTotal -eq
                    [int64]$orcTotalCalculado
                )

            coberturaDataOk =
                (
                    [int64]$orcTotalCalculado -eq
                    (
                        [int64]$orcQtdSerie +
                        [int64]$orcSemDataQtd
                    )
                )
        }

        vendas = [ordered]@{
            fonteTotal = $fonteVendasTotal
            calculadoTotal = $vendasTotalCalculado
            serieComData = $vendasQtdSerie

            semData =
                (
                    [int64]$vendasViaOrcSemDataQtd +
                    [int64]$vendasSemOrcSemDataQtd
                )

            fonteValor =
                Arredondar-Moeda $fonteVendasValor

            calculadoValor =
                $vendasValorCalculado

            serieValorComData =
                $vendasValorSerie

            semDataValor =
                Arredondar-Moeda (
                    [decimal]$vendasViaOrcSemDataValor +
                    [decimal]$vendasSemOrcSemDataValor
                )

            quantidadeOk =
                (
                    [int64]$fonteVendasTotal -eq
                    [int64]$vendasTotalCalculado
                )

            coberturaDataOk =
                (
                    [int64]$vendasTotalCalculado -eq
                    (
                        [int64]$vendasQtdSerie +
                        [int64]$vendasViaOrcSemDataQtd +
                        [int64]$vendasSemOrcSemDataQtd
                    )
                )
        }
    }

    dias = @($diasOrdenados)
    meses = @($mesesOrdenados)
}

Write-Host "Gravando JSON..."

$json =
    $documento |
    ConvertTo-Json -Depth 10

[System.IO.File]::WriteAllText(
    $ArquivoSaida,
    $json,
    (
        New-Object System.Text.UTF8Encoding(
            $false
        )
    )
)

Write-Host ""
Write-Host "==============================================="
Write-Host " SERIE TEMPORAL GERADA"
Write-Host "==============================================="
Write-Host ""
Write-Host "Cobertura:"
Write-Host "  De                      : $dataInicial"
Write-Host "  Ate                     : $dataFinal"
Write-Host "  Dias com movimento      : $($diasOrdenados.Count)"
Write-Host "  Meses com movimento     : $($mesesOrdenados.Count)"
Write-Host ""
Write-Host "ORCAMENTOS:"
Write-Host "  Fonte total             : $fonteOrcTotal"
Write-Host "  Calculado total         : $orcTotalCalculado"
Write-Host "  Com data na serie       : $orcQtdSerie"
Write-Host "  Sem data                : $orcSemDataQtd"
Write-Host "  Quantidade OK           : $($documento.auditoria.orcamentos.quantidadeOk)"
Write-Host "  Cobertura data OK       : $($documento.auditoria.orcamentos.coberturaDataOk)"
Write-Host ""
Write-Host "VENDAS:"
Write-Host "  Fonte total             : $fonteVendasTotal"
Write-Host "  Calculado total         : $vendasTotalCalculado"
Write-Host "  Com data na serie       : $vendasQtdSerie"
Write-Host "  Sem data                : $($documento.auditoria.vendas.semData)"
Write-Host "  Quantidade OK           : $($documento.auditoria.vendas.quantidadeOk)"
Write-Host "  Cobertura data OK       : $($documento.auditoria.vendas.coberturaDataOk)"
Write-Host ""
Write-Host "Arquivo:"
Write-Host $ArquivoSaida
Write-Host ""
Write-Host "OK."
