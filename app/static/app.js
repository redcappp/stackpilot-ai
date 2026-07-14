let schema = null;
const $ = selector => document.querySelector(selector);
const drop = $('#drop'), input = $('#file');
['dragenter', 'dragover'].forEach(event => drop.addEventListener(event, value => { value.preventDefault(); drop.classList.add('over'); }));
['dragleave', 'drop'].forEach(event => drop.addEventListener(event, value => { value.preventDefault(); drop.classList.remove('over'); }));
drop.addEventListener('drop', event => event.dataTransfer.files[0] && upload(event.dataTransfer.files[0]));
input.addEventListener('change', event => event.target.files[0] && upload(event.target.files[0]));

async function upload(file) {
  $('#status').textContent = 'ANALYZING FILE'; $('#status').classList.add('working');
  const form = new FormData(); form.append('file', file);
  try { const response = await fetch('/api/analyze', { method: 'POST', body: form }); if (!response.ok) throw Error((await response.json()).detail); schema = await response.json(); render(); }
  catch (error) { alert(error.message); $('#status').textContent = 'READY TO ANALYZE'; $('#status').classList.remove('working'); }
}

function sampleSchema() {
  const orders = { name: 'customer_order', label: 'Customer Order', source_sheet: 'Orders', rows: 248, columns: [
    { name: 'order_id', label: 'Order ID', type: 'integer', required: true, primary: true }, { name: 'customer_name', label: 'Customer Name', type: 'string', required: true }, { name: 'email', label: 'Email', type: 'email', required: true }, { name: 'order_date', label: 'Order Date', type: 'datetime', required: true }, { name: 'total_amount', label: 'Total Amount', type: 'decimal', required: true }
  ] };
  schema = { project: 'Customer Orders Workspace', source: 'customer_orders.xlsx', rows: 248, entity: orders, entities: [orders], relations: [], sheets: ['Orders'] }; render();
}

function render() {
  const entity = schema.entity, entityCount = (schema.entities || [entity]).length;
  $('#result').classList.remove('hidden'); $('#status').textContent = 'BLUEPRINT READY'; $('#status').classList.remove('working');
  $('#summary').textContent = `We found ${schema.rows.toLocaleString()} records across ${entityCount} data ${entityCount === 1 ? 'model' : 'models'} in ${schema.source}.`;
  $('#entity').innerHTML = `<div class="entity-name">${entity.label}<span>${entity.name}${entityCount > 1 ? ` / +${entityCount - 1} more model${entityCount > 2 ? 's' : ''}` : ''}</span></div>`;
  $('#fields').innerHTML = entity.columns.map(column => `<div class="field"><span class="key">${column.primary ? 'PK' : 'o'}</span><b>${column.name}</b><em>${column.type}</em>${column.required ? '<small>required</small>' : ''}</div>`).join('');
  $('#code').textContent = `@app.get('/api/${entity.name}', dependencies=[Depends(current_user)])\ndef list_${entity.name}(skip: int = 0, limit: int = 50):\n    return db.query(${entity.label.replaceAll(' ', '')}).offset(skip).limit(limit).all()\n\n@app.post('/api/${entity.name}', status_code=201)\ndef create_${entity.name}(payload: ${entity.label.replaceAll(' ', '')}Payload):\n    return create_record(payload)`;
  $('#decision').textContent = schema.relations?.length ? `Detected ${schema.relations.length} possible relationship${schema.relations.length > 1 ? 's' : ''} from ID columns.` : `Configured ${entityCount} protected CRUD resource${entityCount > 1 ? 's' : ''}, type-aware fields, and a React admin dashboard.`;
  $('#result').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

$('#export').addEventListener('click', async () => {
  if (!schema) return;
  const button = $('#export'); button.textContent = 'Packaging...';
  try { const response = await fetch('/api/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(schema) }); if (!response.ok) throw Error('Could not package this project.'); const payload = await response.json(); location.href = payload.download_url; }
  catch (error) { alert(error.message); }
  button.innerHTML = 'Download project <b>down</b>';
});

$('#review').addEventListener('click', async () => {
  if (!schema) return;
  const button = $('#review'); button.textContent = 'Reviewing...';
  try { const response = await fetch('/api/review', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(schema) }); if (!response.ok) throw Error('Architecture review failed.'); const review = await response.json(); $('#review-title').textContent = review.mode === 'gpt-5.6-architecture-review' ? 'GPT-5.6 architecture review' : 'Offline architecture review'; $('#decision').textContent = `${review.summary} ${review.risks?.[0] || review.decisions?.[0] || ''}`; }
  catch (error) { alert(error.message); }
  button.textContent = 'AI architecture review';
});
