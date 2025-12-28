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
function format_percent(value){
    return (value * 100).toFixed(2) + "%"
}
function render_table(strategies){
    html = ""
    for (let i = 0; i < strategies.length; i++) {
        const strategy = strategies[i];
        name = strategy['strategy_name']
        start = strategy['start_date']
        end = strategy['end_date']
        total_return = format_percent(strategy['total_return'])
        max_drawdown = format_percent(strategy['max_drawdown'])
        win_rate = format_percent(strategy['win_rate'])
        html += `<tr><td>${i+1}</td><td>${name}</td><td>${total_return}</td><td>${max_drawdown}</td><td>${win_rate}</td><td>${start}-${end}</td></tr>`
    }
    render("strategy_summary", html)
}

const CHART_THEME = {
    benchmark: '#999999',  // 基准：深灰色
    strategies: [
        '#1890ff', // 科技蓝
        '#2fc25b', // 活力绿
        '#facc14', // 警戒黄
        '#722ed1', // 贵族紫
        '#fa8c16'  // 暖阳橙
    ],
    buy: '#ef5350', // 买入：红色
    sell: '#26a69a' // 卖出：青绿色
};

async function updateBacktest(symbol) {
    myChart.showLoading({text: '正在计算回测收益...', color: CHART_THEME.strategies[0]});

    try{
        const start = document.getElementById("startDate").value;
        const end = document.getElementById("endDate").value;
        const response = await fetch(`/backtest/${symbol}?start=${start}&end=${end}`);
        if (!response.ok) throw new Error("请求失败");
        let res = await response.json();
        if (typeof res === 'string') { res = JSON.parse(res);}
        const actualDates = res.dates;
        const strategies = res.strategies || [];
        const seriesList = [];
        
        // 1. 基准线
        seriesList.push({
            name: res.name,
            type: 'line',
            data: res.benchmark || [],
            lineStyle: {color: CHART_THEME.benchmark, width:2, opacity:0.6},
            symbol: 'none',
            itemStyle: {color: CHART_THEME.benchmark},
            emphasis: { focus: 'series' },
            z: 1
        });

        // 2. 策略线
        strategies.forEach((strat, index) => {
            const color = CHART_THEME.strategies[index % CHART_THEME.strategies.length];
            seriesList.push({
                name: strat.name,
                type: 'line',
                data: strat.equity || [],
                smooth: true,
                z: 2,
                itemStyle: {color: color},
                lineStyle: { width: 2, color: color, shadowColor: 'rgba(0,0,0,0.2)', shadowBlur: 10, shadowOffsetY: 5},
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{
                        offset: 0, color: color + '44' // 25% 不透明度
                    }, {
                        offset: 1, color: color + '00' // 透明
                    }])
                },
                emphasis: { focus: 'series', lineStyle: {width: 4}}, // 鼠标悬浮高亮
                markPoint: {
                    symbol: 'path://M512 0C229.232 0 0 229.232 0 512c0 282.784 229.232 512 512 512 282.784 0 512-229.232 512-512C1024 229.232 794.768 0 512 0z', // 圆形标记
                    symbolSize: 15,
                    data: (strat.signals || []).map(s => ({
                        name: s.type === 'BUY' ? 'B' : 'S',
                        coord: [s.date, s.equity],
                        value: s.type === 'BUY' ? 'B' : 'S',
                        itemStyle: { color: s.type === 'BUY' ? CHART_THEME.buy : CHART_THEME.sell },
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
            backgroundColor: '#ffffff',
            legend: { data: seriesList.map(s => s.name), textStyle:{fontWeight:'bold'}, top: '0%', left: 'center', padding: [10, 0], icon: 'roundRect',},
            grid: {top: '8%', bottom: '12%', left: '2%', right: '2%', containLabel: true,},
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: 'rgba(255, 255, 255, 0.95)', borderWidth: 1, borderColor: '#eee'},
            dataZoom: [{
                type: 'slider', show: true, xAxisIndex: [0], start: 0, end: 100, bottom: '2%', height: 25, borderColor: 'transparent', fillerColor: 'rgba(24, 144, 255, 0.1)',
                handleIcon: 'path://M10.7,11.9v-1.3H9.3v1.3c-4.9,0.3-8.8,4.4-8.8,9.4c0,5,3.9,9.1,8.8,9.4v1.3h1.3v-1.3c4.9-0.3,8.8-4.4,8.8-9.4C19.5,16.3,15.6,12.2,10.7,11.9z M13.3,24.4H6.7V23h6.6V24.4z M13.3,19.6H6.7v-1.4h6.6V19.6z',
                handleSize: '80%', textStyle: { color: '#999' },
                handleStyle: { color: '#fff', shadowBlur: 3, shadowColor: 'rgba(0, 0, 0, 0.6)', shadowOffsetX: 2, shadowOffsetY: 2},
            },{ type: 'inside', xAxisIndex: [0]}
            ],
            xAxis: { type: 'category', data: actualDates, boundaryGap: false, axisLine: { lineStyle: { color: '#ccc' } }},
            yAxis: { scale: true, type: 'value', splitLine:{lineStyle: {type: 'dashed', color: '#f0f0f0'}}, axisLabel:{formatter: (value) => value.toLocaleString()}},
            series: seriesList
        }, true);

        render_table(res.summary_data) 
        render("mainTitle", symbol + "多策略回测对比分析")

    } catch (err) {
        console.error("处理失败:", err);
        myChart.hideLoading();
    }
}

window.addEventListener('resize', () => myChart.resize());
