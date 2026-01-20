let myChart, isChartInit=false
const ui = new UI();
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
    selector.onchange=()=>{const s=selector.value; if(s){currentSymbol=s; updateBacktest(s); document.getElementById('symbol_text').value=s;}};
    if(stocks.length > 0 || symbol != null){
        currentSymbol= (symbol != null ? symbol : stocks[0].symbol);
        selector.value=currentSymbol;
        document.getElementById('symbol_text').value=currentSymbol;
        updateBacktest(currentSymbol);
    }
}

async function doBacktest(symbol=null){
    let sym=symbol||document.getElementById('symbol_text').value.trim()||document.getElementById('stockSelector').value;
    sym=sym.toUpperCase();
    if(!sym){alert('请输入或选择股票代码'); return;} currentSymbol=sym;
    await updateBacktest(sym);
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
    
    $('#kellyInterpretation').html(report.action_guide +'<br>'+ report.logic_interpretation);
    UI.drawKellyGauge("gaugeCanvas", report.suggested_position);
}

function render(tableBodyId, data) {
    const tbody = document.getElementById(tableBodyId);
    tbody.innerHTML = data;
}
function format_percent(value){ return (value * 100).toFixed(2) + "%"}
function format_decimal(value, digits){return value.toFixed(digits)}
function render_table(strategies){
    html = ""
    for (let i = 0; i < strategies.length; i++) {
        const strategy = strategies[i];
        name = strategy['strategy_name']
        start = strategy['start_date']
        end = strategy['end_date']
        total_return = format_percent(strategy['total_return'])
        annual_return = format_percent(strategy['annual_return'])
        max_drawdown = format_percent(strategy['max_drawdown'])
        profit_loss_ratio = format_decimal(strategy['profit_loss_ratio'], 2)
        win_rate = format_percent(strategy['win_rate'])
        trade_win_rate = format_percent(strategy['trade_win_rate'])
        sharpe_ratio = format_decimal(strategy['sharpe_ratio'], 2)
        calmar_ratio = format_decimal(strategy['calmar_ratio'], 2)
        trade_count = strategy['trade_count']
        current_position = strategy['current_position']
        last_trade_pnl = format_percent(strategy['last_trade_pnl'])
        total_days = strategy['total_days']
        trade_days = strategy['trade_days']
        empty_days = strategy['empty_days']
        best_params = strategy['param_config']
        html += `<tr><td>${i+1}</td><td>${name}</td><td>${total_return}</td><td>${annual_return}</td><td>${max_drawdown}</td><td>${profit_loss_ratio}</td><td>${win_rate}</td><td>${trade_win_rate}</td><td>${sharpe_ratio}</td><td>${calmar_ratio}</td><td>${trade_count}</td><td>${current_position}</td><td>${last_trade_pnl}</td><td>${total_days}/${trade_days}/${empty_days}</td><td>${best_params}</td><td>${start}-${end}</td></tr>`
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
        '#fa8c16', // 暖阳橙
        '#13c2c2', // 明亮青
        '#eb2f96', // 酱紫色
        '#a0d911', // 青柠色
        '#fa541c', // 炫赫赤
        '#2f54eb', // 极客蓝
        '#722ed1', // 极光紫
        '#faad14', // 金盏花
        '#52c41a', // 极光绿
        '#0050b3', // 深海蓝
        '#873bf4', // 罗兰紫
        '#006d75', // 瓦松绿
        '#ad8b00', // 橄榄黄
        '#a8071a', // 赭石红
        '#595959', // 中性灰
        '#d9d9d9', // 浅灰色
    ],
    buy: '#ef5350', // 买入：红色
    sell: '#26a69a' // 卖出：青绿色
};

async function updateBacktest(symbol) {
    myChart.showLoading({
        text: `正在计算${symbol}的回测收益...`, 
        color: CHART_THEME.strategies[0],
        textStyle: {
            fontSize: 30,
            fontWeight: 'bold',
        },
        maskColor: 'rgba(255, 255, 255, 0.6)',
    });

    try{
        const start = document.getElementById("startDate").value;
        const end = document.getElementById("endDate").value;
        const mode = document.getElementById('routing').value;
        const response = await fetch(`/backtest/${symbol}?start=${start}&end=${end}&mode=${mode}`);
        if (!response.ok) throw new Error("请求失败");
        let res = await response.json();
        if (typeof res === 'string') { res = JSON.parse(res);}
        const actualDates = res.dates;
        renderReport(symbol, res.report)

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

        // 3. signal table
        ui.renderSignalMatrix(res.signal)

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
const SearchComponent = {
    input: document.getElementById('symbol_text'),
    box: document.getElementById('suggestionBox'),
    debounceTimer: null,
    isComposing: false,
    selectedIndex: -1,
    HISTORY_KEY: 'stock_search_history',
    MAX_HISTORY: 6,

    init() {
        this.bindEvents();
    },

    bindEvents() {
        // IME 中文输入法处理
        this.input.addEventListener('compositionstart', () => this.isComposing = true);
        this.input.addEventListener('compositionend', (e) => {
            this.isComposing = false;
            this.handleInput(e.target.value.trim());
        });

        this.input.addEventListener('input', (e) => {
            if (this.isComposing) return;
            this.handleInput(e.target.value.trim());
        });

        this.input.addEventListener('focus', () => {
            this.input.select();
            if (!this.input.value.trim()) this.renderHistory();
        });

        this.input.addEventListener('keydown', (e) => this.handleKeyDown(e));

        document.addEventListener('click', (e) => {
            if (e.target !== this.input && e.target !== this.box) this.hide();
        });

        this.box.addEventListener('click', (e) => {
            const item = e.target.closest('.suggestion-item');
            if (item) this.confirmSelection(item);
        });
    },

    handleInput(q) {
        clearTimeout(this.debounceTimer);
        if (!q) {
            this.renderHistory();
            return;
        }

        this.debounceTimer = setTimeout(async () => {
            try {
                const response = await fetch(`/api/stocks/search?q=${encodeURIComponent(q)}`);
                const stocks = await response.json();
                this.renderStocks(stocks);
            } catch (err) {
                console.error("搜索失败", err);
            }
        }, 250);
    },

    renderStocks(stocks) {
        if (!stocks.length) {
            this.hide();
            return;
        }
        const html = stocks.map((s, i) => this.getItemHTML(s, i)).join('');
        this.box.innerHTML = html;
        this.show();
    },

    renderHistory() {
        const history = JSON.parse(localStorage.getItem(this.HISTORY_KEY) || '[]');
        if (!history.length) {
            this.hide();
            return;
        }
        const html = `<div class="history-header">最近搜索</div>` + 
                     history.map((s, i) => this.getItemHTML(s, i, true)).join('');
        this.box.innerHTML = html;
        this.show();
    },

    getItemHTML(s, i, isHistory = false) {
        return `
            <div class="suggestion-item" data-index="${i}" 
                 data-symbol="${s.symbol}" data-name="${s.name}" data-market="${s.exchange}">
                <span class="symbol">${isHistory ? '🕒 ' : ''}${s.symbol}</span>
                <span class="name">${s.name}</span>
                <span class="market-tag ${s.exchange}">${s.exchange}</span>
            </div>`;
    },

    handleKeyDown(e) {
        const items = this.box.querySelectorAll('.suggestion-item');
        if (!items.length || this.box.style.display === 'none') {
            if (e.key === 'Enter') doBacktest(this.input.value);
            return;
        }

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            this.selectedIndex = (this.selectedIndex + 1) % items.length;
            this.highlight(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            this.selectedIndex = (this.selectedIndex - 1 + items.length) % items.length;
            this.highlight(items);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (this.selectedIndex > -1) {
                this.confirmSelection(items[this.selectedIndex]);
            } else {
                doBacktest(this.input.value);
                this.hide();
            }
        }
    },

    highlight(items) {
        items.forEach((item, i) => {
            item.classList.toggle('active', i === this.selectedIndex);
            if (i === this.selectedIndex) item.scrollIntoView({ block: 'nearest' });
        });
    },

    confirmSelection(item) {
        const stock = {
            symbol: item.dataset.symbol,
            name: item.dataset.name,
            market: item.dataset.market
        };
        this.input.value = stock.symbol;
        this.saveHistory(stock);
        this.hide();
        if (typeof doBacktest === 'function') doBacktest(stock.symbol);
    },

    saveHistory(stock) {
        let history = JSON.parse(localStorage.getItem(this.HISTORY_KEY) || '[]');
        history = history.filter(h => h.symbol !== stock.symbol);
        history.unshift(stock);
        localStorage.setItem(this.HISTORY_KEY, JSON.stringify(history.slice(0, this.MAX_HISTORY)));
    },

    show() { this.box.style.display = 'block'; this.selectedIndex = -1; },
    hide() { this.box.style.display = 'none'; }
};

SearchComponent.init();

