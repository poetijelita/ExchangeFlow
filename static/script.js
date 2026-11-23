const $ = selector => document.querySelector(selector);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const configs = {
  eps: {title:'EP Tracker', description:'Pantau perjalanan dan perkembangan setiap exchange participant.', singular:'EP', statuses:['Open','Applied','Accepted','Approved','Realized','Finished','Completted'], columns:['Peserta','Program','Negara tujuan','EP Manager','Status','Aksi'], fields:[['name','Nama peserta','text',true],['contact','Kontak','text'],['program','Program','program',true],['destination','Negara tujuan','text'],['manager_id','EP Manager','manager'],['status','Status progres','status'],['pic','PIC lama / catatan penugasan','text'],['notes','Catatan','textarea']]},
  opportunities: {title:'IR Tracker', description:'Kelola peluang internship Global Talent dan Global Teacher.', singular:'peluang', statuses:['Tersedia','Dalam proses','Ditutup'], columns:['Peluang','Program','Negara','Tenggat','Status','Aksi'], fields:[['name','Nama peluang','text',true],['organization','Perusahaan / sekolah','text'],['program','Program','program',true],['country','Negara','text'],['deadline','Tenggat','date'],['status','Status peluang','status'],['link','Tautan lowongan','url'],['notes','Catatan','textarea']]},
  tasks: {title:'To-do List', description:'Catat dan pantau pekerjaan internal EP Manager.', singular:'tugas', statuses:['Belum selesai','Selesai'], columns:['Tugas','EP Manager','Tenggat','Status','Aksi'], fields:[['title','Nama tugas','text',true],['manager_id','EP Manager','manager',true],['due_date','Tenggat','date'],['status','Status','status']]},
  users: {title:'Kelola Akun', description:'Buat akun dan atur peran anggota tim.', singular:'akun', statuses:[], columns:['Nama','Username','Peran'], fields:[['name','Nama lengkap','text',true],['username','Username','text',true],['role','Peran','role',true],['password','Password (minimal 8 karakter)','password',true]]}
};
let view = 'overview', user = null, token = sessionStorage.getItem('exchangeflow_token') || '', editing = null, setupNeeded = false;
let data = {eps:[], opportunities:[], tasks:[], users:[]};
async function api(path, options = {}) {
  const response = await fetch('/api/' + path, {...options, headers:{'Content-Type':'application/json', ...(token ? {'Authorization':'Bearer ' + token} : {}), ...(options.headers || {})}});
  const result = await response.json();
  if (!response.ok) { const error = new Error(result.error || 'Terjadi kesalahan.'); error.status = response.status; throw error; }
  return result;
}
function showError(message) { $('#error').textContent = message; $('#error').hidden = !message; }
function authScreen(setup) {
  setupNeeded = setup; $('#app').hidden = true; $('#auth-screen').hidden = false;
  $('#auth-title').textContent = setup ? 'Buat akun VP' : 'Selamat datang';
  $('#auth-description').textContent = setup ? 'Buat akun pertama untuk mengelola ExchangeFlow dan akun tim.' : 'Masuk untuk melanjutkan pekerjaan tim.';
  $('#auth-name-wrap').hidden = !setup; $('#auth-name-wrap input').required = setup;
  $('#auth-submit').textContent = setup ? 'Buat akun dan masuk' : 'Masuk';
  $('#auth-form').reset(); $('#auth-error').hidden = true;
}
async function boot() {
  try {
    const status = await api('setup-status');
    if (status.needed) return authScreen(true);
    if (!token) return authScreen(false);
    user = await api('me');
    $('#auth-screen').hidden = true; $('#app').hidden = false;
    $('#account-name').textContent = user.name; $('#account-role').textContent = user.role;
    $('#users-nav').hidden = user.role !== 'VP';
    await refresh(); switchView('overview');
  } catch (error) {
    if (error.status === 401) { token = ''; sessionStorage.removeItem('exchangeflow_token'); return authScreen(false); }
    $('#auth-screen').hidden = false; $('#auth-error').textContent = 'Aplikasi tidak terhubung. Pastikan server berjalan lalu muat ulang halaman.'; $('#auth-error').hidden = false;
  }
}
$('#auth-form').addEventListener('submit', async event => {
  event.preventDefault(); const form = event.currentTarget, values = Object.fromEntries(new FormData(form));
  const submit = $('#auth-submit'); submit.disabled = true; $('#auth-error').hidden = true;
  try {
    if (setupNeeded) await api('setup', {method:'POST',body:JSON.stringify(values)});
    const result = await api('login', {method:'POST',body:JSON.stringify(values)});
    token = result.token; sessionStorage.setItem('exchangeflow_token', token); await boot();
  } catch (error) { $('#auth-error').textContent = error.message; $('#auth-error').hidden = false; }
  finally { submit.disabled = false; }
});
$('#logout').addEventListener('click', async () => {
  try { await api('logout', {method:'POST', body:'{}'}); } catch (_) {}
  token = ''; user = null; sessionStorage.removeItem('exchangeflow_token'); authScreen(false);
});
async function refresh() {
  try {
    const [eps, opportunities, tasks, users] = await Promise.all([api('eps'),api('opportunities'),api('tasks'), user.role === 'EP Manager' ? Promise.resolve([]) : api('users')]);
    data = {eps, opportunities, tasks, users}; showError(''); render();
  } catch (error) { if (error.status === 401) { token=''; sessionStorage.removeItem('exchangeflow_token'); authScreen(false); } else showError('Data tidak dapat dimuat. Pastikan aplikasi masih berjalan, lalu muat ulang halaman.'); }
}
function switchView(next) {
  if (next === 'users' && user.role !== 'VP') return;
  view = next; document.querySelectorAll('.nav').forEach(el => el.classList.toggle('active', el.dataset.view === view));
  const overview = view === 'overview', cfg = configs[view];
  $('#breadcrumb').textContent = overview ? 'Overview' : cfg.title;
  $('#title').textContent = overview ? 'Overview' : cfg.title;
  $('#description').textContent = overview ? 'Gambaran pekerjaan dan perkembangan outgoing exchange.' : cfg.description;
  $('#overview-view').hidden = !overview; $('#list-view').hidden = overview;
  const canAdd = !overview && !(view === 'opportunities' && user.role === 'EP Manager') && !(view === 'eps' && user.role === 'EP Manager');
  $('#add-button').hidden = !canAdd;
  if (canAdd) $('#add-button').textContent = `+ Tambah ${cfg.singular}`;
  $('#search').value = ''; $('#program-filter').value = '';
  if (!overview) {
    $('#program-filter').hidden = !['eps','opportunities'].includes(view);
    $('#status-filter').hidden = !cfg.statuses.length;
    $('#status-filter').innerHTML = '<option value="">Semua status</option>' + cfg.statuses.map(s => `<option>${escapeHtml(s)}</option>`).join('');
    $('#table-head').innerHTML = '<tr>' + cfg.columns.map(column => `<th scope="col">${column}</th>`).join('') + '</tr>';
  }
  render();
}
function dateText(value) {
  if (!value) return '—';
  const date = new Date(value + 'T00:00:00');
  return Number.isNaN(date.getTime()) ? escapeHtml(value) : new Intl.DateTimeFormat('id-ID', {day:'numeric',month:'short',year:'numeric'}).format(date);
}
function today() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; }
function overdue(task) { return task.status !== 'Selesai' && task.due_date && task.due_date < today(); }
function renderOverview() {
  const open = data.tasks.filter(t => t.status !== 'Selesai');
  const late = open.filter(overdue);
  const recent = data.eps.slice(0,5);
  const upcoming = [...open].sort((a,b) => (a.due_date || '9999').localeCompare(b.due_date || '9999')).slice(0,5);
  const own = user.role === 'EP Manager';
  $('#overview-view').innerHTML = `<div class="overview-welcome"><div><h2>Halo, ${escapeHtml(user.name)}.</h2><p>${own ? 'Lihat peserta yang Anda dampingi dan tindak lanjut yang perlu dikerjakan.' : 'Pantau peserta, peluang, dan pekerjaan tim dalam satu tempat.'}</p></div><span class="overview-tag">${escapeHtml(user.role)}</span></div>
    <div class="stats"><div class="stat"><span>${own ? 'EP saya' : 'Total EP'}</span><strong>${data.eps.length}</strong><small>peserta tercatat</small></div><div class="stat"><span>Global Talent</span><strong>${data.eps.filter(e=>e.program==='Global Talent').length}</strong><small>peserta</small></div><div class="stat"><span>Tugas terbuka</span><strong>${open.length}</strong><small>belum selesai</small></div><div class="stat"><span>Terlambat</span><strong>${late.length}</strong><small>tugas melewati tenggat</small></div></div>
    <div class="overview-grid"><section class="panel"><div class="panel-head"><h2>Tindak lanjut</h2><button class="text-link" data-go="tasks">Lihat semua</button></div>${upcoming.length ? upcoming.map(t=>`<div class="compact-row"><div><strong>${escapeHtml(t.title)}</strong><small>${escapeHtml(t.manager_name || 'Belum ditugaskan')} · ${dateText(t.due_date)}</small></div><span class="badge ${overdue(t)?'overdue':'status'}">${overdue(t)?'Terlambat':'Terbuka'}</span></div>`).join('') : '<p class="compact-empty">Belum ada tugas terbuka.</p>'}</section>
    <section class="panel"><div class="panel-head"><h2>${own?'EP yang didampingi':'Peserta terbaru'}</h2><button class="text-link" data-go="eps">Lihat semua</button></div>${recent.length ? recent.map(e=>`<div class="compact-row"><div><strong>${escapeHtml(e.name)}</strong><small>${escapeHtml(e.program)} · ${escapeHtml(e.destination || 'Negara belum diisi')}</small></div><span class="badge">${escapeHtml(e.status || 'Belum diatur')}</span></div>`).join('') : '<p class="compact-empty">Belum ada peserta untuk ditampilkan.</p>'}</section></div>`;
}
function render() {
  if (!user) return;
  if (view === 'overview') return renderOverview();
  const query = $('#search').value.trim().toLowerCase(), program = $('#program-filter').value, status = $('#status-filter').value;
  const filtered = data[view].filter(row => (!program || row.program === program) && (!status || row.status === status) && (!query || Object.values(row).some(v => String(v ?? '').toLowerCase().includes(query))));
  $('#result-count').textContent = `${filtered.length} data`;
  $('#table-body').innerHTML = filtered.map(row => {
    if (view === 'users') return `<tr><td class="name-cell">${escapeHtml(row.name)}</td><td>${escapeHtml(row.username)}</td><td><span class="badge">${escapeHtml(row.role)}</span></td></tr>`;
    let cells;
    if (view === 'eps') cells = [`<td class="name-cell">${escapeHtml(row.name)}${row.contact?`<small>${escapeHtml(row.contact)}</small>`:''}</td>`,`<td><span class="badge">${escapeHtml(row.program)}</span></td>`,`<td>${escapeHtml(row.destination || '—')}</td>`,`<td>${escapeHtml(row.manager_name || (row.pic ? row.pic + ' (lama)' : 'Belum ditugaskan'))}</td>`,`<td><span class="badge status">${escapeHtml(row.status || 'Belum diatur')}</span></td>`];
    else if (view === 'opportunities') cells = [`<td class="name-cell">${escapeHtml(row.name)}${row.organization?`<small>${escapeHtml(row.organization)}</small>`:''}</td>`,`<td><span class="badge">${escapeHtml(row.program)}</span></td>`,`<td>${escapeHtml(row.country || '—')}</td>`,`<td>${dateText(row.deadline)}</td>`,`<td><span class="badge status">${escapeHtml(row.status || 'Belum diatur')}</span></td>`];
    else { cells = [`<td class="name-cell">${escapeHtml(row.title)}</td>`,`<td>${escapeHtml(row.manager_name || 'Belum ditugaskan')}</td>`,`<td>${dateText(row.due_date)}</td>`,`<td><span class="badge ${overdue(row)?'overdue':'status'}">${escapeHtml(overdue(row)?'Terlambat':row.status)}</span></td>`]; }
    const readonly = view === 'opportunities' && user.role === 'EP Manager';
    const canDelete = user.role !== 'EP Manager' || view === 'tasks';
    cells.push(`<td><div class="actions"><button class="action" data-action="edit" data-id="${row.id}">${readonly?'Lihat':'Lihat / Ubah'}</button>${canDelete?`<button class="action delete" data-action="delete" data-id="${row.id}">Hapus</button>`:''}</div></td>`);
    return '<tr>' + cells.join('') + '</tr>';
  }).join('');
  $('#empty').hidden = filtered.length > 0;
  $('#empty-title').textContent = data[view].length ? 'Tidak ada data yang cocok' : 'Belum ada data';
  $('#empty-text').textContent = data[view].length ? 'Coba ubah kata kunci atau filter.' : 'Data akan muncul di sini setelah ditambahkan.';
}
function openEditor(record = null) {
  editing = record; const cfg = configs[view], readonly = view === 'opportunities' && user.role === 'EP Manager';
  $('#form-title').textContent = `${readonly?'Detail':record?'Ubah':'Tambah'} ${cfg.singular}`;
  $('#form-error').hidden = true; $('#save-button').hidden = readonly;
  $('#fields').innerHTML = cfg.fields.filter(([name]) => !(['eps','tasks'].includes(view) && user.role === 'EP Manager' && name === 'manager_id')).map(([name,label,type,required]) => {
    const value = record?.[name] ?? (name === 'status' ? cfg.statuses[0] : '');
    let input;
    if (['program','status','manager','ep','role'].includes(type)) {
      let options = type === 'program' ? [['Global Talent','Global Talent'],['Global Teacher','Global Teacher']] : type === 'status' ? cfg.statuses.map(s=>[s,s]) : type === 'role' ? [['EP Manager','EP Manager'],['Team Leader','Team Leader'],['VP','VP']] : type === 'manager' ? [['','Belum ditugaskan'],...data.users.filter(u=>u.role==='EP Manager').map(u=>[u.id,u.name])] : [['','Pilih peserta'],...data.eps.map(e=>[e.id,e.name])];
      if (type === 'status' && value && !options.some(([id]) => id === value)) options = [[value, value + ' (status lama)'], ...options];
      input = `<select id="field-${name}" name="${name}" ${required?'required':''} ${readonly?'disabled':''}>${options.map(([id,text])=>`<option value="${escapeHtml(id)}" ${String(value)===String(id)?'selected':''}>${escapeHtml(text)}</option>`).join('')}</select>`;
    } else if (type === 'textarea') input = `<textarea id="field-${name}" name="${name}" ${readonly?'readonly':''}>${escapeHtml(value)}</textarea>`;
    else input = `<input id="field-${name}" name="${name}" type="${type}" value="${escapeHtml(value)}" ${required?'required':''} ${type==='password'?'minlength="8" autocomplete="new-password"':''} ${readonly?'readonly':''}>`;
    return `<div class="field ${type==='textarea'||type==='url'?'full':''}"><label for="field-${name}">${escapeHtml(label)}${required?' *':''}</label>${input}</div>`;
  }).join('');
  if (readonly && record?.link && /^https?:\/\//i.test(record.link)) $('#fields').insertAdjacentHTML('beforeend', `<div class="field full"><a href="${escapeHtml(record.link)}" target="_blank" rel="noopener noreferrer">Buka tautan lowongan</a></div>`);
  $('#editor').showModal();
}
document.querySelectorAll('.nav').forEach(el=>el.addEventListener('click',()=>switchView(el.dataset.view)));
$('#overview-view').addEventListener('click', event=>{const target=event.target.closest('[data-go]'); if(target) switchView(target.dataset.go);});
['search','program-filter','status-filter'].forEach(id=>$('#'+id).addEventListener('input',render));
$('#add-button').addEventListener('click',()=>openEditor());
$('#close-dialog').addEventListener('click',()=>$('#editor').close()); $('#cancel').addEventListener('click',()=>$('#editor').close());
$('#table-body').addEventListener('click',async event=>{
  const button=event.target.closest('button[data-action]'); if(!button) return;
  const row=data[view].find(item=>item.id===Number(button.dataset.id)); if(!row) return;
  if(button.dataset.action==='edit') return openEditor(row);
  if(confirm(`Hapus “${row.name || row.title}”? Data yang dihapus tidak dapat dikembalikan.`)) {
    try { await api(`${view}/${row.id}`,{method:'DELETE'}); await refresh(); } catch(error){showError(error.message);}
  }
});
$('#record-form').addEventListener('submit',async event=>{
  event.preventDefault(); const payload=Object.fromEntries(new FormData(event.currentTarget)), button=$('#save-button');
  button.disabled=true; $('#form-error').hidden=true;
  try { await api(view+(editing?`/${editing.id}`:''),{method:editing?'PUT':'POST',body:JSON.stringify(payload)}); $('#editor').close(); await refresh(); }
  catch(error){$('#form-error').textContent=error.message;$('#form-error').hidden=false;}
  finally {button.disabled=false;}
});
boot();
