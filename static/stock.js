let chart, candleSeries, volumeSeries, ema5Series, ema20Series;
let scoreChart, scoreLineSeries, priceLineSeries, scoreLineWarning, scoreLineGood;
let currentSymbol='', latestKlines=[];
let isChartInit=false, isScoreChartInit=false;

// ===== 图表初始化 =====
function initChart(){
    const container=document.getElementById('chart');
    chart = LightweightCharts.createChart(container,{width:container.clientWidth,height:600,layout:{background:{color:'#fff'},textColor:'#333'},grid:{vertLines:{color:'#eee'},horzLines:{color:'#eee'}},timeScale:{timeVisible:true}});
    candleSeries=chart.addCandlestickSeries({upColor:'#26a69a',downColor:'#ef5350',borderUpColor:'#26a69a',borderDownColor:'#ef5350',wickUpColor:'#26a69a',wickDownColor:'#ef5350'});
    volumeSeries=chart.addHistogramSeries({color:'#26a69a',priceFormat:{type:'volume'},priceScaleId:'',scaleMargins:{top:0.8,bottom:0}});
    ema5Series=chart.addLineSeries({color:'#f39c12',lineWidth:2});
    ema20Series=chart.addLineSeries({color:'#2980b9',lineWidth:2});
    isChartInit=true;
}
function initScoreChart(){
    const container=document.getElementById('scoreChart');
    scoreChart = LightweightCharts.createChart(container,{width:container.clientWidth,height:300,layout:{background:{color:'#fff'},textColor:'#333'},grid:{vertLines:{color:'#eee'},horzLines:{color:'#eee'}},timeScale:{timeVisible:true},leftPriceScale:{visible:true},rightPriceScale:{visible:true}});
    scoreLineSeries=scoreChart.addLineSeries({priceScaleId:'right',color:getColorByScore(0.2),lineWidth:3,title:'得分',priceLineVisible:false,crosshairMarkerVisible:true});
    priceLineSeries=scoreChart.addLineSeries({priceScaleId:'left',color:'rgba(0,0,0,0.7)',lineWidth:2,title:'📈 收盘价',priceLineVisible:false,crosshairMarkerVisible:true,lineStyle:0});
    scoreLineWarning=scoreChart.addLineSeries({color:getColorByScore(-0.1),lineWidth:1,title:'🐻 离场线',crosshairMarkerVisible:false,lineStyle:0});
    scoreLineGood=scoreChart.addLineSeries({color:getColorByScore(0.7),lineWidth:1,title:'🐮 入场线',crosshairMarkerVisible:false,lineStyle:0});
    isScoreChartInit=true;
}

document.getElementById('toggleSidebar').addEventListener('click',()=>{
    document.getElementById('sidebar').classList.toggle('collapsed');
});

function calculateEMA(data, period){
    const k=2/(period+1), emaArray=[]; let emaPrev=data[0].close;
    data.forEach((d,i)=>{const ema=i===0?d.close:d.close*k+emaPrev*(1-k); emaArray.push(ema); emaPrev=ema;});
    return emaArray;
}
function showReport(text){
    text = marked.parse(getAfterThink(text))
    return text
    .replace(/\b(EMA|ema_short|ema_long)\b/g,m=>`<span style="color:${getRandomFromArray(indicatorColors.EMA)};font-weight:600;">${m}</span>`)
    .replace(/\b(MACD)\b/g,m=>`<span style="color:${getRandomFromArray(indicatorColors.MACD)};font-weight:600;">${m}</span>`)
    .replace(/(?<![A-Za-z0-9])(成交量|VOL)(?![A-Za-z0-9])/g,m=>`<span style="color:${getRandomFromArray(indicatorColors.VOL)};font-weight:600;">${m}</span>`)
    .replace(/(?<![A-Za-z0-9])(趋势)(?![A-Za-z0-9])/g,m=>`<span style="color:${getRandomColor()};font-weight:600;">${m}</span>`)
    .replace(/(?<![A-Za-z0-9])(动量|动能)(?![A-Za-z0-9])/g,m=>`<span style="color:${getRandomColor()};font-weight:600;">${m}</span>`)
    .replace(/(?<![A-Za-z0-9])(价格|price)(?![A-Za-z0-9])/g,m=>`<span style="color:${getRandomFromArray(indicatorColors.PRICE)};font-weight:600;">${m}</span>`)
    .replace(/\b(RSI)\b/g,m=>`<span style="color:${getRandomFromArray(indicatorColors.RSI)};font-weight:600;">${m}</span>`)
    .replace(/\b(KDJ|KD|J)\b/g,m=>`<span style="color:${getRandomFromArray(indicatorColors.KDJ)};font-weight:600;">${m}</span>`)
    .replace(/(?<![A-Za-z0-9])(布林带|BOLL)(?![A-Za-z0-9])/g,m=>`<span style="color:${getRandomFromArray(indicatorColors.BOLL)};font-weight:600;">${m}</span>`)
    .replace(/<score>(.*?)<\/score>/g, (m,p1)=>{const s=parseFloat(p1); const color=getColorByScore(s); return `<div style="margin:4px 0;padding:4px 8px;border-left:3px solid #43a047;background:#f1f8e9;font-size:14px;display:inline-block;">综合评分：<b><span style="color:${color};">${s}</span></b></div>`;})
}
function getAfterThink(text) {const tag = '</think>';const idx = text.indexOf(tag);if(idx === -1) return text;return text.substring(idx + tag.length).trim();}
function getRandomColor(){ const palette=['#42a5f5','#ef5350','#66bb6a','#ab47bc','#ffa726','#26c6da','#ffca28']; return palette[Math.floor(Math.random()*palette.length)]; }
function getRandomFromArray(arr){return arr[Math.floor(Math.random()*arr.length)];}
const indicatorColors={EMA:['#42A5F5','#64B5F6','#90CAF9'],MACD:['#AB47BC','#BA68C8','#CE93D8'],VOL:['#FFA726','#FFB74D','#FFCC80'],PRICE:['#EF5350','#E57373','#EF9A9A'],RSI:['#26C6DA','#4DD0E1','#80DEEA'],KDJ:['#FFD54F','#FFEB3B','#FFF176'],BOLL:['#81D4FA','#4FC3F7','#29B6F6']};
function getColorByScore(score){return score>=0.5?'#27ae60':score>=0.2?'#f1c40f':'#c0392b';}
function parseScoreFromReport(text){try{const m=/<score>\s*([+-]?\d+(\.\d+)?)\s*<\/score>/i.exec(text);if(m&&m[1]) return parseFloat(m[1]);}catch(e){}return null;}
function formatMarketCap(value){ if(!value) return 'N/A'; return (value/1e8).toFixed(2)+'亿'; }
function renderChartBadge(score){
    const existing=document.querySelector('.chart-badge'); if(existing) existing.remove();
    const badge=document.createElement('div');
    badge.className='chart-badge small';
    badge.style.zIndex=9999;
    if(score===null||score===undefined){badge.innerText='评分: -';badge.style.background='#95a5a6';} 
    else {badge.innerText=(score>0?`+${score.toFixed(2)}`:score.toFixed(2)); badge.style.background=getColorByScore(score);}
    document.getElementById('content').appendChild(badge);
}

// ===== 加载股票列表 =====
async function loadStocks(symbol){
    const response=await fetch('/stocks'); if(!response.ok) return;
    const stocks=await response.json();
    const selector=document.getElementById('stockSelector'); selector.innerHTML='<option value="">选择股票</option>';
    stocks.forEach(stock=>{const opt=document.createElement('option'); opt.value=stock.symbol; opt.textContent=`${stock.symbol}`; selector.appendChild(opt);});
    selector.onchange=()=>{const s=selector.value; if(s){currentSymbol=s; searchStock(s); document.getElementById('stockSearch').value=s;}};
    if(stocks.length > 0 || symbol != null){
        currentSymbol= (symbol != null ? symbol : stocks[0].symbol); 
        selector.value=currentSymbol; 
        document.getElementById('stockSearch').value=currentSymbol; 
        searchStock(currentSymbol);
    }
}
// ===== 加载股票信息 =====
async function loadStockInfo(symbol){
    const response=await fetch(`/stock_info/${symbol}`);
    if(!response.ok) return;
    const info=await response.json();
    const detailDiv=document.getElementById('stockInfoDetail');
    detailDiv.innerHTML=`<b>${info.symbol}</b> - ${info.name}<br>行业: <b>${info.industry||'未知'}</b> | 市值:<b>${formatMarketCap(info.market_cap)}</b><br>info: ${info.info||'-'}`;
    const summaryDiv=document.getElementById('stockInfoSummary');
    summaryDiv.onclick=()=>{if(detailDiv.style.display==='none'){detailDiv.style.display='block'; summaryDiv.innerText='点击收起股票基本信息';} else {detailDiv.style.display='none'; summaryDiv.innerText='点击查看股票基本信息';}};
}
// ===== 查询股票 =====
async function searchStock(symbol=null){
    let sym=symbol||document.getElementById('stockSearch').value.trim()||document.getElementById('stockSelector').value;
    sym=sym.toUpperCase();
    if(!sym){alert('请输入或选择股票代码'); return;} currentSymbol=sym;
    const interval=document.getElementById('intervalSelector').value;
    const start_date = document.getElementById("startDate").value;
    const end_date = document.getElementById("endDate").value; 
    await loadStockInfo(sym);
    const response=await fetch(`/klines/${sym}?interval=${interval}&start_date=${start_date}&end_date=${end_date}`);
    if(!response.ok){alert('未找到该股票的K线数据'); return;}
    const klines=await response.json(); latestKlines=klines;
    const formatted=klines.map(k=>({time:k.date,open:k.open,high:k.high,low:k.low,close:k.close}));
    candleSeries.setData(formatted); chart.timeScale().fitContent();
    const volData=klines.map(k=>({time:k.date,value:k.volume,color:k.close>=k.open?'#26a69a':'#ef5350'}));
    volumeSeries.setData(volData);
    const ema5=calculateEMA(formatted,5); const ema20=calculateEMA(formatted,20);
    ema5Series.setData(formatted.map((d,i)=>({time:d.time,value:ema5[i]})));
    ema20Series.setData(formatted.map((d,i)=>({time:d.time,value:ema20[i]})));
    document.getElementById('chartTitle').innerHTML = `<span class="gradient-title">${currentSymbol} K线图</span>`;
    document.getElementById('scoreChartTitle').innerHTML = `<span class="gradient-title">${currentSymbol} 分析报告得分</span>`;

    const reportResp=await fetch(`/quant_report/${sym}?start_date=${start_date}&end_date=${end_date}`); let reportData=[];
    if(reportResp.ok){ reportData=await reportResp.json();}
    const tbody=document.getElementById('customTableBody'); tbody.innerHTML='';
    const tableHead = document.querySelector('#customTable thead tr th');
    tableHead.colSpan = 4;
    tableHead.innerHTML = `<span class="gradient-title">${currentSymbol} 股票分析报告</span>`;

    if(reportData.length>0){
        reportData.sort((a,b)=>new Date(b.date)-new Date(a.date));
        const headerTr=document.createElement('tr');
        headerTr.style.textAlign='center'; 
        headerTr.innerHTML=`<th>日期</th><th>收盘价</th><th>得分</th><th>📊滤网报告📊</th>`;
        tbody.appendChild(headerTr);
        latest_score = parseScoreFromReport(reportData[0].three_filters_report)
        renderChartBadge(latest_score) 
        reportData.forEach(row=>{
            const tr=document.createElement('tr');
            tr.innerHTML=`
                <td style="width:120px"><b>${row.date}</b></br>更新:${row.update_time}</td>
                <td style="width:80px"><b>${row.price?.toFixed(2)||'-'}</b></td>
                <td style="color:${getColorByScore(row.three_filters_score)}; font-size:30px">${row.three_filters_score??'-'}</td>
                <td style="vertical-align: top;">${showReport(row.three_filters_report)||'-'}</td>`;
            tbody.appendChild(tr);
        });

        const priceData = reportData.filter(r=>r.three_filters_score!==null).map(r=>({time:r.date,value:r.price?.toFixed(2)})).sort((a,b)=>new Date(a.time)-new Date(b.time));
        const scoreData = reportData.filter(r=>r.three_filters_score!==null).map(r=>({time:r.date,value:parseFloat(r.three_filters_score)})).sort((a,b)=>new Date(a.time)-new Date(b.time));
        warningData = scoreData.map(d => ({ ...d, value: 0.0 }));
        goodData = scoreData.map(d => ({ ...d, value: 0.7 }));
        if(scoreData.length>0){priceLineSeries.setData(priceData);scoreLineSeries.setData(scoreData);scoreLineWarning.setData(warningData);scoreLineGood.setData(goodData);scoreChart.timeScale().fitContent();}
    } else { tbody.innerHTML='<tr><td>暂无分析报告</td></tr>'; }
}

function getParam(name) {
  const searchParams = new URLSearchParams(window.location.search);
  const hashParams = new URLSearchParams(window.location.hash.split("?")[1]);
  return searchParams.get(name) || hashParams.get(name);
}

// 初始化
document.addEventListener('DOMContentLoaded',()=>{
    if(!isChartInit) initChart();
    if(!isScoreChartInit) initScoreChart();
    const end_date = new Date();
    const start_date = new Date(end_date.getTime() - 60 * 24 * 60 * 60 * 1000);
    document.getElementById("startDate").value = start_date.toISOString().slice(0, 10);
    document.getElementById("endDate").value = end_date.toISOString().slice(0, 10);
    loadStocks(getParam("symbol"));
});
window.onresize=()=>{
    if(chart) chart.applyOptions({width:document.getElementById('chart').clientWidth});
    if(scoreChart) scoreChart.applyOptions({width:document.getElementById('scoreChart').clientWidth});
};

