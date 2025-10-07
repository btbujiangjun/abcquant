import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from db import QuantDB
from utils.logger import logger

app = FastAPI()
db = QuantDB()

# ===================
# 前端页面
# ===================
@app.get("/", response_class=HTMLResponse)
def get_index():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>股票K线分析系统</title>
        <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
        <style>
            body { font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#f4f6f8; margin:0; padding:20px; }
            .container { max-width:1200px; margin:auto; background:white; padding:20px; border-radius:10px; box-shadow:0 2px 10px rgba(0,0,0,0.1); }
            h1 { text-align:center; color:#2c3e50; }
            .toolbar { display:flex; gap:10px; margin-bottom:20px; }
            input,select,button { padding:10px; border:1px solid #ccc; border-radius:4px; }
            input { flex:1; }
            button { background-color:#3498db; color:white; border:none; cursor:pointer; }
            button:hover { background-color:#2980b9; }
            #chart { height:600px; margin-top:20px; }
            #stockInfo { background:#f8f9fa; border-radius:8px; padding:10px; margin-bottom:15px; font-size:14px; color:#555; line-height:1.6; cursor:pointer; }
            #customTable { width:100%; border-collapse: collapse; margin-top:20px; font-size:14px; }
            #customTable th, #customTable td { border:1px solid #ccc; padding:8px; text-align:left; }
            #customTable th { background:#f0f0f0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📈 股票K线查询系统</h1>
            <div class="toolbar">
                <select id="stockSelector"></select>
                <input type="text" id="stockSearch" placeholder="输入股票代码或名称搜索">
                <select id="intervalSelector">
                    <option value="1min">1分钟</option>
                    <option value="5min">5分钟</option>
                    <option value="15min">15分钟</option>
                    <option value="30min">30分钟</option>
                    <option value="60min">1小时</option>
                    <option value="daily" selected>日线</option>
                    <option value="weekly">周线</option>
                    <option value="monthly">月线</option>
                </select>
                <button onclick="searchStock()">查询</button>
            </div>

            <div id="stockInfo">
                <div id="stockInfoSummary">点击查看股票基本信息</div>
                <div id="stockInfoDetail" style="display:none;"></div>
            </div>

            <div id="chart"></div>

            <!-- 分析报告表格 -->
            <table id="customTable">
                <thead>
                    <tr><th colspan="10">分析报告</th></tr>
                </thead>
                <tbody id="customTableBody">
                    <tr><td>请选择股票加载分析报告</td></tr>
                </tbody>
            </table>
        </div>

        <script>
        let chart, candleSeries, volumeSeries, ema5Series, ema20Series;
        let currentSymbol = '';
        let latestKlines = [];

        function initChart(){
            chart = LightweightCharts.createChart(document.getElementById('chart'), {
                width: document.getElementById('chart').clientWidth,
                height:600,
                layout:{background:{color:'#fff'}, textColor:'#333'},
                grid:{vertLines:{color:'#eee'}, horzLines:{color:'#eee'}},
                timeScale:{timeVisible:true}
            });

            candleSeries = chart.addCandlestickSeries({
                upColor:'#26a69a', downColor:'#ef5350',
                borderUpColor:'#26a69a', borderDownColor:'#ef5350',
                wickUpColor:'#26a69a', wickDownColor:'#ef5350',
            });

            volumeSeries = chart.addHistogramSeries({
                color:'#26a69a', priceFormat:{type:'volume'},
                priceScaleId:'', scaleMargins:{top:0.8,bottom:0}
            });

            ema5Series = chart.addLineSeries({color:'#f39c12', lineWidth:2});
            ema20Series = chart.addLineSeries({color:'#2980b9', lineWidth:2});

            const toolTip = document.createElement('div');
            toolTip.style.cssText = 'position:absolute;background:rgba(255,255,255,0.95);border:1px solid #ccc;border-radius:5px;padding:8px;font-size:13px;color:#333;pointer-events:none;display:none;';
            document.body.appendChild(toolTip);

            chart.subscribeCrosshairMove(param=>{
                if(!param.point || !param.time){ toolTip.style.display='none'; return; }
                const price = param.seriesPrices.get(candleSeries);
                if(!price){ toolTip.style.display='none'; return; }

                let html = `<b>${param.time}</b><br>
                            O: ${price.open.toFixed(2)} H: ${price.high.toFixed(2)}<br>
                            L: ${price.low.toFixed(2)} C: ${price.close.toFixed(2)}<br>
                            V: ${volumeSeries.dataAt(param.time)?.value || '-'}`;
                const ema5 = param.seriesPrices.get(ema5Series);
                const ema20 = param.seriesPrices.get(ema20Series);
                if(ema5) html += `<br>EMA5: ${ema5.toFixed(2)}`;
                if(ema20) html += `<br>EMA20: ${ema20.toFixed(2)}`;

                const rect = document.getElementById('chart').getBoundingClientRect();
                toolTip.innerHTML = html;
                toolTip.style.display='block';
                toolTip.style.left = Math.min(rect.right - 150, rect.left + param.point.x + 15) + 'px';
                toolTip.style.top = Math.max(rect.top, rect.top + param.point.y - 80) + 'px';
            });
        }

        function calculateEMA(data, period){
            const k = 2/(period+1);
            const emaArray = [];
            let emaPrev = data[0].close;
            data.forEach((d,i)=>{
                const ema = i===0?d.close:d.close*k+emaPrev*(1-k);
                emaArray.push(ema);
                emaPrev=ema;
            });
            return emaArray;
        }

        function getColorByScore(score) {
            if(score >= 0.5) return '#27ae60';       // 高分绿
            else if(score >= 0.2) return '#f1c40f';  // 中等黄
            else return '#c0392b';                  // 低分红
        }

        async function loadStocks(){
            const response = await fetch('/stocks');
            const stocks = await response.json();
            const selector = document.getElementById('stockSelector');
            selector.innerHTML = '<option value="">选择股票</option>';
            stocks.forEach(stock=>{
                const opt = document.createElement('option');
                opt.value = stock.symbol;
                opt.textContent = `${stock.symbol} - ${stock.name}`;
                selector.appendChild(opt);
            });
            selector.onchange = ()=>{ 
                const s=selector.value; 
                if(s){ 
                    currentSymbol = s;
                    searchStock(s);
                    document.getElementById('stockSearch').value = s
                } 
            };
            if(stocks.length>0){ 
                currentSymbol = stocks[0].symbol;
                selector.value = currentSymbol;
                document.getElementById('stockSearch').value = currentSymbol;
                searchStock(currentSymbol);
            }
        }

        function formatMarketCap(value){
            if(!value) return 'N/A';
            return (value / 1e8).toFixed(2) + '亿';
        }

        async function loadStockInfo(symbol){
            const response = await fetch(`/stock_info/${symbol}`);
            if(!response.ok) return;
            const info = await response.json();
            const detailDiv = document.getElementById('stockInfoDetail');
            detailDiv.innerHTML = `
                <b>${info.symbol}</b> - ${info.name}<br>
                行业: ${info.industry||'未知'} | 市值: ${formatMarketCap(info.market_cap)}<br>
                info: ${info.info || '-'}
            `;
            const summaryDiv = document.getElementById('stockInfoSummary');
            summaryDiv.onclick = ()=>{
                if(detailDiv.style.display === 'none'){
                    detailDiv.style.display = 'block';
                    summaryDiv.innerText = '点击收起股票基本信息';
                } else {
                    detailDiv.style.display = 'none';
                    summaryDiv.innerText = '点击查看股票基本信息';
                }
            };
        }

        async function searchStock(symbol=null){
            const sym = symbol || document.getElementById('stockSearch').value.trim() || document.getElementById('stockSelector').value;
            const interval = document.getElementById('intervalSelector').value;
            if(!sym){ alert('请输入或选择股票代码'); return; }
            currentSymbol = sym;

            await loadStockInfo(sym);

            const response = await fetch(`/klines/${sym}?interval=${interval}`);
            if(!response.ok){ alert('未找到该股票的K线数据'); return; }
            const klines = await response.json();
            latestKlines = klines;
            const formatted = klines.map(k=>({time:k.date,open:k.open,high:k.high,low:k.low,close:k.close}));
            candleSeries.setData(formatted);
            chart.timeScale().fitContent();
            const volData = klines.map(k=>({time:k.date,value:k.volume,color:k.close>=k.open?'#26a69a':'#ef5350'}));
            volumeSeries.setData(volData);

            const ema5 = calculateEMA(formatted,5);
            const ema20 = calculateEMA(formatted,20);
            ema5Series.setData(formatted.map((d,i)=>({time:d.time,value:ema5[i]})));
            ema20Series.setData(formatted.map((d,i)=>({time:d.time,value:ema20[i]})));

            // 获取分析报告
            const reportResp = await fetch(`/quant_report/${sym}`);
            let reportData = [];
            if(reportResp.ok){
                reportData = await reportResp.json();
            }

            // 更新分析报告表格，按日期倒序
            const tbody = document.getElementById('customTableBody');
            tbody.innerHTML = '';
            if(reportData.length > 0){
                reportData.sort((a,b)=> new Date(b.date) - new Date(a.date));
                // 表头
                const headerTr = document.createElement('tr');
                headerTr.innerHTML = `
                    <th>日期</th>
                    <th>收盘价</th>
                    <th>📊滤网</th>
                    <th>滤网报告</th>
                    <th>🔽双底</th>
                    <th>双底报告</th>
                    <th>🔼双顶</th>
                    <th>双顶报告</th>
                    <th>🏺杯柄</th>
                    <th>杯柄报告</th>
                `;
                tbody.appendChild(headerTr);

                reportData.forEach(row=>{
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${row.date}</td>
                        <td>${row.price?.toFixed(2) || '-'}</td>
                        <td style="color:${getColorByScore(row.three_filters_score)}; font-size: 20px">${row.three_filters_score ?? '-'}</td>
                        <td>${row.three_filters_report || '-'}</td>
                        <td style="color:${getColorByScore(row.double_bottom_score)}; font-size: 20px">${row.double_bottom_score ?? '-'}</td>
                        <td>${row.double_bottom_report || '-'}</td>
                        <td style="color:${getColorByScore(row.double_top_score)}; font-size: 20px">${row.double_top_score ?? '-'}</td>
                        <td>${row.double_top_report || '-'}</td>
                        <td style="color:${getColorByScore(row.cup_handle_score)}; font-size: 20px">${row.cup_handle_score ?? '-'}</td>
                        <td>${row.cup_handle_report || '-'}</td>
                    `;
                    tbody.appendChild(tr);
                });
            } else {
                tbody.innerHTML = '<tr><td>暂无分析报告</td></tr>';
            }
        }

        document.addEventListener('DOMContentLoaded', ()=>{
            document.getElementById('intervalSelector').onchange = ()=>{
                if(currentSymbol) searchStock(currentSymbol);
            };
        });

        window.onload = ()=>{initChart(); loadStocks(); };
        window.onresize = ()=>chart.applyOptions({width:document.getElementById('chart').clientWidth});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# ===================
# 后端接口
# ===================
@app.get("/stocks")
def get_us_stocks():
    df = db.query_stock_base(exchange="us", top_k=500)
    print("Stock base DF:", df.head())
    if df.empty: return []
    return [{"symbol": row["symbol"], "name": row["name"]} for _, row in df.iterrows()]

@app.get("/klines/{symbol}")
def get_klines(symbol: str, interval: str="daily"):
    df = db.query_stock_price(symbol, interval=interval)
    if df.empty:
        raise HTTPException(status_code=404, detail="未找到该股票的K线数据")
    return [{"date": row["date"].split()[0], "open":float(row["open"]), "high":float(row["high"]),
             "low":float(row["low"]), "close":float(row["close"]), "volume":float(row.get("volume",0))} for _, row in df.iterrows()]

@app.get("/quant_report/{symbol}")
def get_analysis_report(symbol: str):
    df = db.query_analysis_report(symbol, score_only=False)
    if df.empty:
        raise HTTPException(status_code=404, detail="未找到该股票信息")
    df = df.sort_values('date', ascending=False)  # 日期倒序
    return [{
        "symbol": row["symbol"],
        "date": row["date"].split()[0], 
        "price": row["close"],
        "three_filters_score": row.get("three_filters_score"),
        "three_filters_report": row.get("three_filters_report"),
        "double_bottom_score": row.get("double_bottom_score"),
        "double_bottom_report": row.get("double_bottom_report"),
        "double_top_score": row.get("double_top_score"),
        "double_top_report": row.get("double_top_report"),
        "cup_handle_score": row.get("cup_handle_score"),
        "cup_handle_report": row.get("cup_handle_report")
    } for _, row in df.iterrows()]

@app.get("/stock_info/{symbol}")
def get_stock_info(symbol: str):
    df = db.query_stock_info(symbol)
    if df.empty:
        raise HTTPException(status_code=404, detail="未找到该股票信息")
    row = df.iloc[0]
    return {"symbol":row["symbol"],"name":row["name"],"industry":row.get("industry"),"market_cap":row.get("market_cap"),"info":row.get("info")}

if __name__=="__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
