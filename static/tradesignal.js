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
    strategies: ["Alpha_One", "Trend_Follower", "Grid_Strategy", "AI_Sentiment", "Scalper_Pro"],
    minStreak: 3
};

let currentDataStore = [];

/**
 * 1. 动态生成表头
 */
function initTableHeader() {
    const $header = $('#headerRow');
    $header.find('th:not(:first-child)').remove(); // 清空旧表头
    CONFIG.strategies.forEach(s => $header.append(`<th>${s}</th>`));
}
function updateTableHeader(strategies) {
    const $header = $('#headerRow');
    // 保留第一个 "Date" 列，移除之后的所有列
    $header.find('th:gt(0)').remove(); 
    strategies.forEach(s => {
        $header.append(`<th>${s.replace(/_/g, ' ')}</th>`); // 顺便把下划线转为空格美化
    });
}
/**
 * 2. 核心：从后端加载数据
 */
async function loadData(symbol=null) {
    $('#loadingTxt').show();
    let sym = symbol||document.getElementById('stockSearch').value.trim()||document.getElementById('stockSelector').value;
    symbol = sym.toUpperCase();
    try {
        const response = await fetch(`/api/tradesignal/${symbol}`);
        const rawStrategies = await response.json(); 
        
        const strategyNames = rawStrategies.map(s => s.strategy_name);
        CONFIG.strategies = strategyNames;
        updateTableHeader(strategyNames);

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

/**
 * 3. 渲染矩阵
 */
function renderMatrix() {
    let html = "";
    currentDataStore.forEach((row, rowIndex) => {
        html += `<tr><td class="sticky-date">${row.date}</td>`;
        
        CONFIG.strategies.forEach((stratName) => {
            // 如果某天该策略没有信号，默认显示 HOLD 或中性状态
            const sig = row.signals[stratName] || "HOLD";
            
            // 计算 Streak 的逻辑保持不变，但要检查 row.signals[stratName]
            let streak = calculateStreak(sig, rowIndex, stratName);

            let alertClass = "";
            let prefix = "";
            if (rowIndex === 0 && sig !== "HOLD" && streak >= CONFIG.minStreak) {
                alertClass = sig === "BUY" ? "latest-strong-buy" : "latest-strong-sell";
                prefix = streak >= 5 ? "🔥 " : "✨ ";
            }

            const icon = sig === 'BUY' ? '▲' : (sig === 'SELL' ? '▼' : '■');
            const streakLabel = (streak > 1 && sig !== "HOLD") ? `<span class="streak-badge">${streak}D</span>` : "";

            html += `<td>
                <span class="sig-tag ${sig.toLowerCase()} ${alertClass}">
                    ${prefix}${icon} ${sig}${streakLabel}
                </span>
            </td>`;
        });
        html += "</tr>";
    });
    $('#matrixBody').html(html);
}

/**
 * 计算连续天数（逻辑解耦）
 */
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
    initTableHeader();
    loadStocks(getParam("symbol"))
});

