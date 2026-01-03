let currentSymbol = '', has_loadStocks = false

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

const CONFIG = {
    strategies: [],
    minStreak: 3,
    strong_Streak: 5,
};

let currentDataStore = [];

const fmt = (val, isPct = false, isCss = true) => {
    if (val == null) return '--';
    const v = isPct ? (val * 100).toFixed(2) + '%' : val.toFixed(2);
    const cls = isPct ? (val > 0 ? 'text-pos' : 'text-neg') : '';
    return isCss ? `<span class="${cls}">${v}</span>` : `<span>${v}</span>`;
};

/**
 * 绘制凯利头寸仪表盘
 * @param {number} value - 凯利数值 (0.0 到 1.0)
 */
function drawKellyGauge(value) {
    const canvas = document.getElementById('gaugeCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const centerX = canvas.width / 2;
    const centerY = canvas.height - 20;
    const radius = 100;

    // 清空画布
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 1. 绘制背景圆弧 (灰色底色)
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, Math.PI, 2 * Math.PI);
    ctx.lineWidth = 12;
    ctx.strokeStyle = '#f1f5f9';
    ctx.stroke();

    // 2. 绘制激活区间 (渐变色：从浅绿到深绿)
    if (value > 0) {
        ctx.beginPath();
        // 限制最大值 1.0
        const endAngle = Math.PI + (Math.min(value, 1) * Math.PI);
        ctx.arc(centerX, centerY, radius, Math.PI, endAngle);
        ctx.lineWidth = 12;
        const gradient = ctx.createLinearGradient(0, 0, canvas.width, 0);
        gradient.addColorStop(0, '#86efac'); // 浅绿
        gradient.addColorStop(1, '#16a34a'); // 深绿
        ctx.strokeStyle = gradient;
        ctx.stroke();
    }

    // 3. 绘制指针
    const angle = Math.PI + (Math.min(Math.max(value, 0), 1) * Math.PI);
    const pointerLen = radius - 15;
    
    ctx.save();
    ctx.translate(centerX, centerY);
    ctx.rotate(angle);
    
    ctx.beginPath();
    ctx.moveTo(0, -4);
    ctx.lineTo(pointerLen, 0);
    ctx.lineTo(0, 4);
    ctx.fillStyle = '#1e293b'; // 深色指针
    ctx.fill();
    
    // 轴心圆点
    ctx.beginPath();
    ctx.arc(0, 0, 6, 0, Math.PI * 2);
    ctx.fillStyle = '#1e293b';
    ctx.fill();
    ctx.restore();
}

function render_strategy_score(tableBodyId, data_items) {
  const tbody = document.getElementById(tableBodyId);
  tbody.innerHTML = ""; 
  if (!data_items || data_items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4">暂无数据</td></tr>`;
    return;
  }

  const items = Object.entries(data_items)
    .sort((a, b) => b[1].weight - a[1].weight) // 按权重从高到低排序
  items.forEach(([name, data], index) => {
    const tr = document.createElement("tr");
    const weightPct = (data.weight * 100).toFixed(1) + '%';
    const org_score = data.weight.toFixed(2)
    tr.innerHTML = ` 
      <td>${index + 1}</td>
      <td>${name}</td>
      <td>${weightPct}</td>
      <td>${org_score}</td>
    `;
    tbody.appendChild(tr);
  }); 
}

function render_score_analysis(tableBodyId, data_items) {
  const tbody = document.getElementById(tableBodyId);
  tbody.innerHTML = "";
  if (!data_items || data_items.length === 0) {
    tbody.innerHTML = `<tr><td>暂无数据</td></tr>`;
    return;
  }

  data_items.forEach((data, index) => {
    const tr = document.createElement("tr");
    tr.innerHTML = ` 
      <td style="text-align: left;">${data}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderReport(symbol, report){
    $('#kellyOps').text(report.signal);
    $('#kellyPos').text((report.suggested_position * 100).toFixed(1) + "%");
    $('#kellyScore').text(report.signal_score.toFixed(2));
    $('#kellyConfience').text(report.confidence_score);
    const opsEl = $('#kellyOps');
    const posEl = $('#kellyPos');
    if (opsEl.text() === 'BUY' || opsEl.text() === 'HOLD') {
        opsEl.addClass('text-buy').removeClass('text-sell');
        posEl.addClass('text-buy').removeClass('text-sell');
    } else {
        opsEl.addClass('text-sell').removeClass('text-buy');
        posEl.addClass('text-sell').removeClass('text-buy');
    }

    const td = document.getElementById('dynamic_risk_management');   
    td.innerHTML = report.dynamic_risk_management.join('</br>') || ""
 
    $('#kellyAction').text(report.action_guide);
    drawKellyGauge(report.suggested_position);
    render_strategy_score('strategy_score', report.strategy_weights)
    render_score_analysis('strategy_analysis', report.contribution_analysis)
}

function renderStat(label, value) {
    return (
        '<div class="stat-item">' +
            '<span class="stat-label">' + label + '</span>' +
            '<span class="stat-value">' + value + '</span>' +
        '</div>'
    );
}

function renderRatioStat(label, mainValue, ratioValue) {
    return (
        '<div class="stat-item">' +
            '<span class="stat-label">' + label + '</span>' +
            '<span class="stat-value">' +
                mainValue + '(' + ratioValue + ')' +
            '</span>' +
        '</div>'
    );
}

function updateTableHeader(strategies) {
    const $header = $('#headerRow');
    const $stats  = $('#statsRow');

    $header.find('th:gt(0)').remove();
    $stats.empty();

    strategies.forEach(s => {
        const perf = s.perf || {};

        // ===== 表头 =====
        $header.append(
            '<th>' + s.strategy_class.replace(/_/g, ' ') + '</th>'
        );

        const totalDays  = perf.total_days || 0;
        const tradeDays  = perf.trade_days || 0;
        const emptyDays  = totalDays - tradeDays;

        const tradeRatio = totalDays > 0 ? tradeDays / totalDays : 0;
        const emptyRatio = totalDays > 0 ? emptyDays / totalDays : 0;

        // ===== 指标区 =====
        const html = [
            '<th class="stats-th">',

            renderStat('总收益',     fmt(perf.total_return, true)),
            renderStat('年化收益',   fmt(perf.annual_return, true)),
            renderStat('最大回撤',   fmt(perf.max_drawdown, true)),
            renderStat('盈亏比',     fmt(perf.profit_loss_ratio, false)),
            renderStat('夏普比率',   fmt(perf.sharpe_ratio, false)),
            renderStat('卡玛比率',   fmt(perf.calmar_ratio, false)),
            renderStat('按天胜率',   fmt(perf.win_rate, true)),
            renderStat('按笔胜率',   fmt(perf.trade_win_rate, true)),
            renderStat('交易笔数',   perf.trade_count ?? '-'),
            renderStat('持仓状态',   perf.current_position ?? '-'),
            renderStat('最近盈利',   fmt(perf.last_trade_pnl, true)),
            renderStat('交易天数',   totalDays),

            renderRatioStat(
                '持仓天数',
                tradeDays,
                fmt(tradeRatio, true, false)
            ),

            renderRatioStat(
                '空仓天数',
                emptyDays,
                fmt(emptyRatio, true, false)
            ),

            '</th>'
        ].join('');

        $stats.append(html);
    });
}

async function loadData(symbol=null) {
    $('#loadingTxt').show();
    let sym = symbol||document.getElementById('stockSearch').value.trim()||document.getElementById('stockSelector').value;
    symbol = sym.toUpperCase();
    try {
        const response = await fetch(`/api/tradesignal/${symbol}`);
        const result = await response.json(); 
        rawStrategies = result["signal"]
        report = result["report"]
        renderReport(symbol, result["report"])
        rawStrategies.sort((a, b) => (b.perf.annual_return || 0) - (a.perf.annual_return || 0));

        console.log(report)

        const strategyNames = rawStrategies.map(s => s.strategy_name);
        CONFIG.strategies = strategyNames;
        updateTableHeader(rawStrategies);

        const matrixMap = {};
        rawStrategies.forEach(strat => {
            const name = strat.strategy_name;
            strat.equity_df.forEach(item => {
                const rawDate = item.date;
                const date = typeof rawDate === 'string' ? rawDate.split('T')[0] : rawDate;
                if (!matrixMap[date]) {
                    matrixMap[date] = { date: date, signals: {} };
                }
                const signal = item.signal == 1 ? "BUY" : (item.signal == -1 ? "SELL" : "HOLD");
                matrixMap[date].signals[name] = signal || "HOLD";
            });
        });

        currentDataStore = Object.values(matrixMap).sort((a, b) => 
            b.date.localeCompare(a.date)
        );

        renderMatrix();
    } catch (err) {
        console.error("加载失败:", err);
        $('#matrixBody').html('<tr><td colspan="100">暂无有效信号数据</td></tr>');
    } finally {
        $('#loadingTxt').hide();
    }
}

function renderMatrix() {
    let html = "";
    currentDataStore.forEach((row, rowIndex) => {
        html += `<tr><td class="sticky-date">${row.date}</td>`;
        CONFIG.strategies.forEach((stratName) => {
            const sig = row.signals[stratName] || "HOLD";
            let streak = calculateStreak(sig, rowIndex, stratName);
            let alertClass = "";
            let prefix = "";
            if (rowIndex === 0 && sig !== "HOLD" && streak >= CONFIG.minStreak) {
                alertClass = sig === "BUY" ? "pulse-buy" : "pulse-sell";
                prefix = streak >= CONFIG.strong_Streak ? "🔥 " : "✨ ";
            }
            const icon = sig === 'BUY' ? '▲' : (sig === 'SELL' ? '▼' : '■');
            const streakLabel = (streak > 1 && sig !== "HOLD") ? `<span class="streak-badge">(${streak}D)</span>` : "";
            html += `<td><span class="sig-tag ${sig.toLowerCase()} ${alertClass}">${prefix}${icon} ${sig}${streakLabel}</span></td>`;
        });
        html += "</tr>";
    });
    $('#matrixBody').html(html);
}
function calculateStreak(sig, rowIndex, stratName) {
    if (sig === "HOLD") return 1;
    let streak = 1;
    // 往下找（更旧的日期）
    for (let k = rowIndex + 1; k < currentDataStore.length; k++) {
        if (currentDataStore[k].signals[stratName] === sig) {
            streak++;
        } else {
            break;
        }
    }
    return streak;
}

$(document).ready(() => {
    loadStocks(getParam("symbol"))
});
