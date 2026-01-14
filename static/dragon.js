document.addEventListener('DOMContentLoaded',()=>{
    const now = new Date();
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    document.getElementById("datePicker").value = yesterday.toISOString().slice(0, 10);
    loadDragon();
});
document.getElementById("datePicker").addEventListener('change', loadDragon);
function updateDateLabels(date) {
  ["Gainers","Losers","TopReport","BottomReport",].forEach(id=>{
    document.getElementById("date"+id).textContent = date;
  });
}
async function loadDragon() {
  const date = document.getElementById("datePicker").value;
  const keyword = document.getElementById("dragonSearch").value.trim();
  const resp = await fetch(`/api/dragon?date=${date}&query=${encodeURIComponent(keyword)}`);
  const data = await resp.json();
  renderGrowthTop10("TopGainers10Body", data.Top_Gainers);
  renderGrowthTop10("TopLosers10Body", data.Top_Losers);
  renderTop10("Top_Report10Body", data.Top_Report);
  renderTop10("Bottom_Report10Body", data.Bottom_Report);
  updateDateLabels(date)
}

function renderGrowthTop10(tableBodyId, items) {
  const tbody = document.getElementById(tableBodyId);
  tbody.innerHTML = "";
  if (!items || items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7">暂无数据</td></tr>`;
    return;
  }

  items.forEach((item, index) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${index + 1}</td>
      <td><a href="/?symbol=${item.symbol}">${item.symbol}</a></td>
      <td>${item.prev_close}</td>
      <td>${item.latest_close}</td>
      <td>${item.pct}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderTop10(tableBodyId, items) {
  const tbody = document.getElementById(tableBodyId);
  tbody.innerHTML = "";
  if (!items || items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4">暂无数据</td></tr>`;
    return;
  }

  items.forEach((item, index) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${index + 1}</td>
      <td><a href="/?symbol=${item.symbol}">${item.symbol}</a></td>
      <td>${item.prev_score}</td>
      <td style="color:${item.score>item.prev_score ? '#27ae60':'#c0392b'}">${item.score}</td>
    `;
    tbody.appendChild(tr);
  });
}



