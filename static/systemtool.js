document.addEventListener('DOMContentLoaded',()=>{
  const selector=document.getElementById('database');
  selector.onchange=()=>{
    load_metadata()
  }
  load_metadata();
});
async function load_metadata() {
  const database = document.getElementById("database").value;
  const resp = await fetch(`/api/systemtool?cli=table&database=${database}`);
  const data = await resp.json();

  const select = document.getElementById("datatable");
  if (!select) return;
  select.innerHTML = '';
  data.forEach(item => {
    const option = document.createElement('option');
    option.value = item;
    option.textContent = item;
    select.appendChild(option);
  });
}

async function load_data() {
  const database = document.getElementById("database").value;
  const datatable = document.getElementById("datatable").value;
  const sql = document.getElementById("sql").value;
  const resp = await fetch(`/api/systemtool?cli=query&database=${database}&datatable=${datatable}&sql=${sql}`);
  const data = await resp.json();
  
  /* ---------- 表头 ---------- */
  let theadHtml = '<tr>';
  data.columns.forEach(col => {theadHtml += `<th>${col}</th>`;});
  theadHtml += '</tr>';
  document.getElementById('tableHead').innerHTML = theadHtml;

  /* ---------- 表体 ---------- */
  let tbodyHtml = '';
  data.rows.forEach(row => {
    tbodyHtml += '<tr>';
    data.columns.forEach(col => {
        const val = row[col] ?? '';
        tbodyHtml += `<td>${val}</td>`;
    });
    tbodyHtml += '</tr>';
  });
  document.getElementById('tableBody').innerHTML = tbodyHtml;
}



