(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  let config, rows = [], rev, selected = -1, dirty = false, busy = false;
  const bridge = window.AstrBotPluginView;
  function ask(message) {
    return new Promise(resolve => {
      const dialog = $('confirmDialog'); $('confirmText').textContent = message;
      dialog.returnValue = 'cancel';
      $('cancelConfirm').onclick = () => dialog.close('cancel');
      $('acceptConfirm').onclick = () => dialog.close('yes');
      dialog.onclose = () => resolve(dialog.returnValue === 'yes');
      dialog.showModal();
    });
  }
  function error(message = '') { $('error').textContent = message; $('error').hidden = !message; }
  function changed() { dirty = true; $('saveState').textContent = '有未保存修改'; $('save').disabled = busy; $('previewText').hidden = true; $('matchResult').textContent = ''; }
  function draft() { return {...config, enabled: $('enabled').checked, injection_mode: $('injection').value, relations_json: JSON.stringify(rows)}; }
  function renderList() {
    $('count').textContent = rows.length;
    $('people').replaceChildren();
    const query = $('search').value.trim().toLowerCase();
    rows.forEach((row, index) => {
      if (query && !(row.label + row.qq).toLowerCase().includes(query)) return;
      const button = document.createElement('button'); button.type = 'button'; button.className = 'nav' + (selected === index ? ' active' : '');
      const name = document.createElement('span'); name.textContent = row.label || '未命名人物';
      const qq = document.createElement('small'); qq.textContent = (row.qq || '待填写 QQ') + (row.enabled ? '' : '（已停用）');
      button.append(name, qq); button.onclick = () => select(index); $('people').append(button);
    });
    if (!$('people').children.length) { const note = document.createElement('p'); note.className = 'hint'; note.textContent = rows.length ? '没有匹配的人物' : '还没有专属关系。点击「新增」，为一个 QQ 设置例外。'; $('people').append(note); }
  }
  function modeHint() {
    const replace = $('mode').value === 'replace';
    $('fusionPane').hidden = replace;
    $('modeHint').textContent = replace ? '上方填写完整人格；不会补入原人格。关系与称呼作为新人格的明确字段保留。' : '将修改要求融合进基础人格，检查下方完整结果后保存。聊天只使用融合结果。';
  }
  function select(index) {
    selected = index; $('globalPane').hidden = index >= 0; $('personPane').hidden = index < 0;
    $('globalTab').classList.toggle('active', index < 0);
    if (index >= 0) { const r = rows[index]; for (const key of ['qq','label','relation','address','mode']) $(key).value = r[key];
      $('personPrompt').value = r.prompt; $('basePersona').value = r.base_id || ''; $('compiled').value = r.compiled || ''; $('personEnabled').checked = r.enabled; $('personTitle').textContent = r.label || '新人物'; $('previewQQ').value = r.qq; modeHint();
    } else $('previewQQ').value = '';
    $('previewText').hidden = true; $('matchResult').textContent = ''; renderList();
  }
  function apply(data) {
    $('basePersona').replaceChildren(new Option('请选择基础人格', '')); for (const p of data.personas || []) $('basePersona').add(new Option(p.id, p.id));
    config = data.config; rows = JSON.parse(config.relations_json); rev = data.revision;
    $('enabled').checked = config.enabled;
    $('injection').value = config.injection_mode;
    dirty = false; $('saveState').textContent = '已保存 · 下一条消息生效'; select(selected >= rows.length ? -1 : selected);
  }
  async function run(action) {
    if (busy) return; busy = true; error();
    document.querySelectorAll('input,textarea,select,button').forEach(el => el.disabled = true);
    try { await action(); } catch (e) { error(e.message || '操作失败，请重试'); }
    finally { busy = false; document.querySelectorAll('input,textarea,select,button').forEach(el => el.disabled = !config); $('reload').disabled = false; }
  }
  $('globalTab').onclick = () => select(-1);
  $('search').oninput = renderList;
  $('add').onclick = () => { rows.push({qq:'',label:'',relation:'',address:'',mode:'inherit',prompt:'',enabled:true,base_id:'',compiled:'',compiled_key:''}); changed(); select(rows.length-1); $('qq').focus(); };
  for (const key of ['qq','label','relation','address','mode']) $(key).addEventListener('input', () => {
    rows[selected][key] = $(key).value; changed();
    if (key === 'qq') $('previewQQ').value = $(key).value;
    if (key === 'label') $('personTitle').textContent = $(key).value || '新人物';
    modeHint(); renderList();
  });
  $('personPrompt').oninput = () => { rows[selected].prompt = $('personPrompt').value; changed(); };
  $('basePersona').onchange = () => { rows[selected].base_id = $('basePersona').value; changed(); };
  $('compiled').oninput = () => { rows[selected].compiled = $('compiled').value; changed(); };
  $('compile').onclick = () => run(async () => { const data = await bridge.apiPost('compile', {config:draft(),qq:rows[selected].qq}); Object.assign(rows[selected], data); $('compiled').value = data.compiled; changed(); $('saveState').textContent = '融合草稿已生成 · 检查后保存'; });
  $('personEnabled').onchange = () => { rows[selected].enabled = $('personEnabled').checked; changed(); renderList(); };
  for (const key of ['enabled','injection']) $(key).addEventListener('input', changed);
  $('delete').onclick = async () => { if (await ask('删除这个人物关系？保存后生效。')) { rows.splice(selected,1); changed(); select(-1); } };
  $('save').onclick = () => run(async () => { const index = selected; const data = await bridge.apiPost('settings', {config:draft(),revision:rev}); selected = index; apply(data); });
  $('reload').onclick = async () => { if (!dirty || await ask('重新载入会丢弃未保存修改，继续吗？')) run(async () => apply(await bridge.apiGet('settings'))); };
  $('preview').onclick = () => run(async () => {
    const data = await bridge.apiPost('preview', {config:draft(),qq:$('previewQQ').value.trim()});
    $('matchResult').textContent = !data.prompt ? '沿用当前 AstrBot 人格（未匹配或已停用）' : data.matched ? '这是保存后发送给模型的完整人格' : '未命中人物关系，沿用当前 AstrBot 人格';
    $('previewText').textContent = data.prompt || '未替换人格，实际人格由当前会话决定。'; $('previewText').hidden = false;
  });
  window.addEventListener('beforeunload', e => { if(dirty) {e.preventDefault(); e.returnValue = '';} });
  run(async () => { if(!bridge) throw new Error('请从 AstrBot 插件卡片的「打开视图」进入。'); await Promise.race([bridge.ready(),new Promise((_,reject) => setTimeout(() => reject(new Error('连接超时，请从插件卡片重新打开视图。')),12000))]); apply(await bridge.apiGet('settings')); });
})();

