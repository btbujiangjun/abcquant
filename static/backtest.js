let myChart, isChartInit=false
document.addEventListener('DOMContentLoaded',()=>{
    initDateSelector()
    loadStocks()
    if(!isChartInit) initChart()
});
function initChart(){
    const chartDom = document.getElementById('backtest-container');
    myChart = echarts.init(chartDom);
    isChartInit=true
}
function initDateSelector(){
    const end_date = new Date();
    const start_date = new Date(end_date.getTime() - 720 * 24 * 60 * 60 * 1000);
    document.getElementById("startDate").value = start_date.toISOString().slice(0, 10);
    document.getElementById("endDate").value = end_date.toISOString().slice(0, 10);
}
async function loadStocks(symbol){
    const response=await fetch('/stocks'); if(!response.ok) return;
    const stocks=await response.json();
    const selector=document.getElementById('stockSelector'); selector.innerHTML='<option value="">选择股票</option>';
    stocks.forEach(stock=>{const opt=document.createElement('option'); opt.value=stock.symbol; opt.textContent=`${stock.symbol}`; selector.appendChild(opt);});
    selector.onchange=()=>{const s=selector.value; if(s){currentSymbol=s; updateBacktest(s); document.getElementById('stockSearch').value=s;}};
    if(stocks.length > 0 || symbol != null){
        currentSymbol= (symbol != null ? symbol : stocks[0].symbol);
        selector.value=currentSymbol;
        document.getElementById('stockSearch').value=currentSymbol;
        updateBacktest(currentSymbol);
    }
}

async function searchBacktest(symbol=null){
    let sym=symbol||document.getElementById('stockSearch').value.trim()||document.getElementById('stockSelector').value;
    sym=sym.toUpperCase();
    if(!sym){alert('请输入或选择股票代码'); return;} currentSymbol=sym;
    await updateBacktest(sym);
}

function render(tableBodyId, data) {
    const tbody = document.getElementById(tableBodyId);
    tbody.innerHTML = data;
}

async function updateBacktest(symbol) {
    myChart.showLoading({ text: '数据计算中...' });

    try {
        const start = document.getElementById("startDate").value;
        const end = document.getElementById("endDate").value;
        const response = await fetch(`/backtest/${symbol}?start=${start}&end=${end}`);
        if (!response.ok) throw new Error("请求失败");
        let res = await response.json();
        if (typeof res === 'string') {
            res = JSON.parse(res);
        }
        const actualDates = res.dates;
        const strategies = res.strategies || []; // 防止 strategies 不存在时报错
        const seriesList = [];
        
        // 1. 基准线
        seriesList.push({
            name: '基准指数',
            type: 'line',
            data: res.benchmark || [],
            lineStyle: { type: 'dashed', color: '#999' },
            symbol: 'none'
        });

        // 2. 策略线 (增加安全检查)
        strategies.forEach(strat => {
            seriesList.push({
                name: strat.name,
                type: 'line',
                width: 3,
                data: strat.equity || [],
                smooth: true,
                markPoint: {
                    data: (strat.signals || []).map(s => ({
                        name: s.type === 'BUY' ? '买入' : '卖出',
                        coord: [s.date, s.equity],
                        value: s.type,
                        itemStyle: { color: s.type === 'BUY' ? '#ef5350' : '#26a69a' }
                    }))
                }
            });
        });

        myChart.hideLoading();

        // 3. 渲染检查
        if (!actualDates || actualDates.length === 0) {
            console.error("数据为空或日期字段名不匹配 (res.datas/res.dates)");
            return;
        }

        myChart.setOption({
            tooltip: { trigger: 'axis' },
            xAxis: { 
                type: 'category',
                data: actualDates 
            },
            yAxis: { scale: true },
            series: seriesList
        }, true);

        // 4.摘要
        render("strategy_summary", res.summary_table) 
        render("mainTitle", symbol + "多策略回测对比分析")

    } catch (err) {
        console.error("处理失败:", err);
        myChart.hideLoading();
    }
}

window.addEventListener('resize', () => myChart.resize());
