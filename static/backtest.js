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
                lineStyle: { 
                    width: 2, 
                    color: color,
                    shadowColor: 'rgba(0,0,0,0.2)',
                    shadowBlur: 10,
                    shadowOffsetY: 5
                },
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
            grid: {top: '8%', left: '2%', right: '2%', containLabel: true,},
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: 'rgba(255, 255, 255, 0.95)', borderWidth: 1, borderColor: '#eee'},
            xAxis: { type: 'category', data: actualDates, boundaryGap: false, axisLine: { lineStyle: { color: '#ccc' } }},
            yAxis: { scale: true, type: 'value', splitLine:{lineStyle: {type: 'dashed', color: '#f0f0f0'}}, axisLabel:{formatter: (value) => value.toLocaleString()}},
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
