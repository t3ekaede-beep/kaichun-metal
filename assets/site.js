{
  // 手機選單：把目前這一頁捲到看得到的位置
  const cur = document.querySelector('nav.main [aria-current="page"]');
  if (cur && cur.offsetLeft + cur.offsetWidth > cur.parentElement.clientWidth) cur.parentElement.scrollLeft = cur.offsetLeft - 16;

  // 車款照片：維基偶爾一次擋太多張，失敗就等一下重試一次，再失敗換成剪影
  const sil = () => {
    const d = document.createElement('div');
    d.innerHTML = '<svg class="sil" viewBox="0 0 300 110" aria-hidden="true"><use href="#sil"/></svg>';
    return d.firstChild;
  };
  const retry = img => {
    if (!img.dataset.retry) {
      img.dataset.retry = '1';
      setTimeout(() => { img.src = img.src + '&retry=1'; }, 1500 + Math.random() * 2000);
    } else {
      img.replaceWith(sil());
    }
  };
  for (const img of document.querySelectorAll('.ph img')) {
    img.addEventListener('error', () => retry(img));
    if (img.complete && img.naturalWidth === 0 && img.getAttribute('src')) retry(img);
  }

  // 複製詢價格式（客戶須知頁）
  const cb = document.getElementById('copyBtn');
  if (cb) {
    const msg = document.getElementById('copyMsg');
    const fmt = document.getElementById('fmt');
    cb.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(fmt.innerText);
        msg.textContent = '已複製，貼到 LINE 就可以';
      } catch (e) {
        const r = document.createRange();
        r.selectNodeContents(fmt);
        const s = window.getSelection();
        s.removeAllRanges();
        s.addRange(r);
        msg.textContent = '已選取，請按複製';
      }
    });
  }

  // 篩選：搜尋框＋品牌＋車型（常收車款、場內車源）
  for (const box of document.querySelectorAll('.filters')) {
    const list = document.querySelector(box.dataset.target);
    if (!list) continue;
    const items = [...list.children];
    const q = box.querySelector('input[type=search]');
    const count = box.parentElement.querySelector('.count');
    const none = box.parentElement.querySelector('.empty-filter');
    const state = {};
    const apply = () => {
      const text = (q && q.value || '').trim().toLowerCase();
      let shown = 0;
      for (const el of items) {
        let ok = !text || (el.dataset.search || '').includes(text);
        for (const k in state) if (state[k] && el.dataset[k] !== state[k]) ok = false;
        el.hidden = !ok;
        if (ok) shown++;
      }
      if (count) count.textContent = `${shown} 筆`;
      if (none) none.hidden = shown > 0;
    };
    for (const group of box.querySelectorAll('.chips')) {
      const key = group.dataset.key;
      group.addEventListener('click', e => {
        const b = e.target.closest('.chip');
        if (!b) return;
        const on = b.getAttribute('aria-pressed') !== 'true';
        for (const x of group.querySelectorAll('.chip')) x.setAttribute('aria-pressed', 'false');
        b.setAttribute('aria-pressed', on ? 'true' : 'false');
        state[key] = on ? b.dataset.v : '';
        apply();
      });
    }
    if (q) q.addEventListener('input', apply);
    apply();
  }
}
