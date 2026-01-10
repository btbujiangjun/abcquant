let currentSymbol = '', has_loadStocks = false
const ui = new UI();
async function loadStocks(symbol){
    const response=await fetch('/stocks'); if(!response.ok) return;
    const stocks=await response.json();
    const selector=document.getElementById('stockSelector');
    selector.innerHTML='<option value="">选择股票</option>';
    stocks.forEach(stock=>{
        const opt=document.createElement('option'); 
        opt.value=stock.symbol;
        opt.textContent=`${stock.symbol}`; 
        selector.appendChild(opt);
    });
    selector.onchange=()=>{
        const s=selector.value; 
        if(s){
            currentSymbol=s; 
            loadData(s); 
            document.getElementById('stockSearch').value=s;
        }
    };
    if(stocks.length > 0 || symbol != null){
        currentSymbol= (symbol != null ? symbol : stocks[0].symbol); 
        selector.value=currentSymbol; 
        document.getElementById('stockSearch').value=currentSymbol; 
        loadData(currentSymbol);
    }   
}

function getParam(name) {
    const searchParams = new URLSearchParams(window.location.search);
    const hashParams = new URLSearchParams(window.location.hash.split("?")[1]);
    return searchParams.get(name) || hashParams.get(name);
}

function render_strategy_score(tableBodyId, data_items, summary) {
  const tbody = document.getElementById(tableBodyId);
  tbody.innerHTML = ""; 
  if (!data_items || data_items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4">暂无数据</td></tr>`;
    return;
  }

  const items = Object.entries(data_items)
    .sort((a, b) => b[1].annual_return - a[1].annual_return) // 按权重从高到低排序
  items.forEach(([name, data], index) => {
    const tr = document.createElement("tr");
    name = data[0], data = data[1]
    const weight = ((data.weight || 0) * 100).toFixed(1);
    const annual_return = ((data.annual_return || 0) * 100).toFixed(2)
    const win_adj = ((data.win_adj || 0) * 100).toFixed(2)
    const reliability = data.reliability.toFixed(2)
    const alpha = data.alpha.toFixed(2)
    const calmar_ratio = data.calmar_ratio.toFixed(2)
    const risk = data.risk.toFixed(2)
    const recent_std = data.recent_std.toFixed(2)
    const pnl = ((data.pnl || 0) * 100).toFixed(2)
    const state = data.state.toFixed(2)
    const penalty = data.penalty.toFixed(2)
    const vol = data.vol.toFixed(2)
    html = ` 
      <td>${index + 1}</td>
      <td>${name.replace(/Strategy/g, '')}</td>
      <td>${weight}%</td>
      <td>${annual_return}%</td>
      <td>${win_adj}%</td>
      <td>${reliability}</td>
      <td>${alpha}</td>
      <td>${calmar_ratio}</td>
      <td>${risk}</td>
      <td>${recent_std}</td>
      <td>${pnl}%</td>
      <td>${state}</td>
      <td>${penalty}</td>
      <td>${vol}</td>
    `;
    if(index == 0){
        const rows = items.length
        const avg_p = summary.avg_p.toFixed(2)
        const avg_b = summary.avg_b.toFixed(2)
        const kelly_f_orig = summary.kelly_f_orig.toFixed(2)
        const diversity_score = summary.diversity_score.toFixed(2)
        const ensemble_signal = summary.ensemble_signal.toFixed(2)
        const confidence_factor = summary.confidence_factor.toFixed(2)
        const kelly_f = summary.kelly_f.toFixed(2)
        const target_risk_ratio = summary.target_risk_ratio.toFixed(2)
        const raw_pos_size = ((summary.raw_pos_size || 0) * 100).toFixed(1)
        const suggested_pos = ((summary.suggested_pos || 0 ) * 100).toFixed(1)
        const current_pos = ((summary.current_pos || 0) * 100).toFixed(1)
        const exec_status = summary.exec_status
        html += `
          <td rowspan='${rows}'>${avg_p}</td>
          <td rowspan='${rows}'>${avg_b}</td>
          <td rowspan='${rows}'>${kelly_f_orig}</td>
          <td rowspan='${rows}'>${diversity_score}</td>
          <td rowspan='${rows}'>${ensemble_signal}</td>
          <td rowspan='${rows}'>${confidence_factor}</td>
          <td rowspan='${rows}'>${kelly_f}</td>
          <td rowspan='${rows}'>${target_risk_ratio}</td>
          <td rowspan='${rows}'>${raw_pos_size}%</td>
          <td rowspan='${rows}'>${suggested_pos}%</td>
          <td rowspan='${rows}'>${current_pos}%</td>
          <td rowspan='${rows}'>${exec_status}</td>
        `;
    }
    tr.innerHTML = html 
    tbody.appendChild(tr);
  }); 
}

function renderReport(symbol, report){
    $('#kellySymbol').html(`<a href="/?symbol=${symbol}">${symbol}</a>`)
    $('#kellyOps').text(report.signal);
    $('#kellyPos').text((report.suggested_position * 100).toFixed(1) + "%");
    $('#kellyScore').text(report.signal_score.toFixed(2));
    $('#kellyConfience').text(report.confidence_score);
    const opsEl = $('#kellyOps');
    const posEl = $('#kellyPos');
    if (opsEl.text() === 'BUY' || opsEl.text() === 'STRONG_BUY') {
        opsEl.addClass('text-buy').removeClass('text-sell');
        posEl.addClass('text-buy').removeClass('text-sell');
    } else {
        opsEl.addClass('text-sell').removeClass('text-buy');
        posEl.addClass('text-sell').removeClass('text-buy');
    }

    const td = document.getElementById('dynamic_risk_management');   
    td.innerHTML = [...report.dynamic_risk_management,...report.contribution_analysis].join('</br>') || ""
    $('#kellyAction').text(report.action_guide);
    $('#kellyInterpretation').text(report.logic_interpretation);
    UI.drawKellyGauge("gaugeCanvas", report.suggested_position);
    render_strategy_score('strategy_score', report.trace_items, report.trace_summary)
}

async function loadData(symbol=null) {
    $('#loadingTxt').show();
    let sym = symbol||document.getElementById('stockSearch').value.trim()||document.getElementById('stockSelector').value;
    symbol = sym.toUpperCase();
    try {
        const response = await fetch(`/api/tradesignal/${symbol}`);
        const result = await response.json(); 
        rawStrategies = result["signal"]
        renderReport(symbol, result["report"])
        ui.renderSignalMatrix(result["signal"])
    } catch (err) {
        console.error("加载失败:", err);
        $('#matrixBody').html('<tr><td colspan="100">暂无有效信号数据</td></tr>');
    } finally {
        $('#loadingTxt').hide();
    }
}

$(document).ready(() => {
    loadStocks(getParam("symbol"))
});
