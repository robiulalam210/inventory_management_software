/*
 * বাকি খাতা — দোকান খাতার মূল পেজ (TallyKhata / Khatabook ধরনের সহজ খাতা)।
 *
 * কোনো নতুন হিসাব-নিয়ম নেই, সব পুরনো API:
 *   /api/customers-active/                  সব কাস্টমার + total_due / advance_balance (Customers পেজের একই হিসাব)
 *   /api/reports/customer-due-reminders/    কার বাকি কত দিনের, মেমো, তৈরি তাগাদা-বার্তা (Due Reminders পেজের একই)
 *   /api/money-receipts/summary/            আজ কত আদায়
 *   /api/reports/customer-ledger/           একজনের খাতা, চলমান বাকি সহ
 *   POST /api/money-receipts/               টাকা পেলাম → Money Receipt → Transaction → Account (টাকা ঢোকার একমাত্র পথ)
 *   POST /api/customers/                    নতুন কাস্টমার
 *
 * দুই ভাষা: L('English', 'বাংলা') — <html data-lang> অনুযায়ী (i18n.js)। বাংলায় অঙ্কও বাংলা (৳ ১২,৩৪৫);
 * টাইপ করার ঘরে ইংরেজি অঙ্কই চলে। কাস্টমারকে পাঠানো তাগাদা/ধন্যবাদ বার্তা সবসময় বাংলায় (কাস্টমার পড়বেন)।
 */
(function () {
  'use strict';

  const n = (v) => { const x = Number(v); return isFinite(x) ? x : 0; };
  const round2 = (v) => Math.round(v * 100) / 100;
  const pad = (x) => String(x).padStart(2, '0');
  const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const DAY = 86400000;
  const SENT_KEY = 'dueRemind.sent';   // Due Reminders পেজের সাথে একই — দুই জায়গায় "তাগাদা পাঠানো হয়েছে" মেলে

  const BN = document.documentElement.getAttribute('data-lang') === 'bn';
  const L = (en, bn) => (BN ? bn : en);
  const bnNum = new Intl.NumberFormat('bn-BD', { maximumFractionDigits: 2 });   // বার্তায় (সবসময় বাংলা)
  const numFmt = new Intl.NumberFormat(BN ? 'bn-BD' : 'en-IN', { maximumFractionDigits: 2 });
  const intFmt = new Intl.NumberFormat(BN ? 'bn-BD' : 'en-IN', { maximumFractionDigits: 0 });
  const MONTHS = BN ? ['জানুয়ারি', 'ফেব্রুয়ারি', 'মার্চ', 'এপ্রিল', 'মে', 'জুন', 'জুলাই', 'আগস্ট', 'সেপ্টেম্বর', 'অক্টোবর', 'নভেম্বর', 'ডিসেম্বর']
    : ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const METHODS = [
    { value: 'Cash', label: L('Cash', 'ক্যাশ') },
    { value: 'Mobile banking', label: L('bKash/Nagad', 'বিকাশ/নগদ') },
    { value: 'Bank', label: L('Bank', 'ব্যাংক') },
  ];
  const ICON = (d) => `<svg class="ic" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;

  const store = {
    get(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { window.localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
  };
  const listOf = (r) => { const d = r && r.data; return Array.isArray(d) ? d : ((d && (d.results || d.customers)) || []); };

  // বাংলাদেশি নম্বর → 8801XXXXXXXXX (wa.me এর জন্য)। ভুল হলে ''
  function intlPhone(p) {
    let d = String(p || '').replace(/\D/g, '');
    if (d.startsWith('00')) d = d.slice(2);
    if (d.length === 11 && d.startsWith('01')) d = '88' + d;
    else if (d.length === 10 && d.startsWith('1')) d = '880' + d;
    return /^8801\d{9}$/.test(d) ? d : '';
  }

  window.khata = function (init) {
    return {
      perms: init.perms || {},
      urls: init.urls || {},
      me: init.me,
      shop: init.shop || {},
      methods: METHODS,
      icons: { up: ICON('<path d="M12 19.5v-15M5.5 11 12 4.5 18.5 11"/>'), down: ICON('<path d="M12 4.5v15M5.5 13l6.5 6.5 6.5-6.5"/>') },
      L,
      tabs: [{ key: 'due', label: L('Owe you', 'বাকি আছে') }, { key: 'all', label: L('Everyone', 'সবাই') }, { key: 'advance', label: L('Advance', 'অগ্রিম') }],
      sorts: [{ key: 'amount', label: L('Most owed', 'বেশি বাকি') }, { key: 'age', label: L('Oldest due', 'পুরনো বাকি') }, { key: 'name', label: L('Name', 'নাম') }],

      rows: [], loading: true, error: '',
      sum: { due: 0, dueCount: 0, advance: 0, advanceCount: 0, oldest: 0, over30: 0, today: null, todayCount: 0 },
      f: { q: '', tab: 'due', sort: 'amount' },
      sel: null,
      ledger: { rows: [], loading: false, error: '', totDebit: 0, totCredit: 0 },
      accounts: [],
      sent: {},
      pay: { open: false, cid: '', lockCustomer: false, amount: '', method: 'Cash', account: '', date: '', note: '', saving: false, error: '', err: {}, done: null },
      nc: { open: false, name: '', phone: '', address: '', opening: '', saving: false, error: '', err: {} },
      due: { open: false, cid: '', kind: 'credit', amount: '', date: '', note: '', saving: false, error: '', err: {} },
      dueMap: {},        // entry_no → { id, can_delete } — খাতার লাইনে মোছার বোতামের জন্য
      delDue: null,
      toast: '', _toast: null, _lreq: 0,
      todayIso: iso(new Date()),

      init() {
        try { this.sent = JSON.parse(store.get(SENT_KEY) || '{}') || {}; } catch (e) { this.sent = {}; }
        this.load().then(() => {
          if (init.open) { const r = this.rows.find(x => String(x.id) === String(init.open)); if (r) this.open(r); }
        });
        if (this.perms.collect) {
          App.api('/api/accounts/', { query: { no_pagination: 'true' } })
            .then(r => { this.accounts = listOf(r).filter(a => a.is_active !== false); this.pickAccount(); }).catch(() => {});
        }
        this.$watch('pay.method', () => this.pickAccount());
        this.$watch('pay.cid', () => { this.pay.err = {}; this.pay.error = ''; });
        // ফোনে খাতা খোলা থাকলে পেছনের পাতা স্ক্রল হয় না
        this.$watch('sel', (v) => document.documentElement.classList.toggle('kh-lock', !!v && window.matchMedia('(max-width: 1100px)').matches));
      },

      // ───────── তালিকা ─────────
      async load() {
        this.error = '';
        const t = this.todayIso;
        try {
          const [all, due, today] = await Promise.all([
            App.api('/api/customers-active/'),
            App.api('/api/reports/customer-due-reminders/').catch(() => null),
            this.perms.receipts ? App.api('/api/money-receipts/summary/', { query: { start_date: t, end_date: t } }).catch(() => null) : Promise.resolve(null),
          ]);
          const dueMap = {};
          ((due && due.data && due.data.customers) || []).forEach(d => { dueMap[d.customer_id] = d; });
          this.rows = listOf(all).filter(c => c.is_active !== false).map(c => {
            const d = dueMap[c.id];
            return {
              id: c.id, name: c.name || '', phone: c.phone || '', client_no: c.client_no || '',
              due: round2(n(c.total_due)), advance: round2(n(c.advance_balance)),
              days: d ? n(d.days_overdue) : null,
              invoices: d ? (d.invoices || []) : [],
              message: d ? d.message : '',
              last: d ? d.last_sale_date : null,
            };
          });
          const owing = this.rows.filter(r => r.due > 0);
          const adv = this.rows.filter(r => r.advance > 0);
          this.sum = {
            due: round2(owing.reduce((s, r) => s + r.due, 0)), dueCount: owing.length,
            advance: round2(adv.reduce((s, r) => s + r.advance, 0)), advanceCount: adv.length,
            oldest: Math.max(0, ...owing.map(r => r.days || 0)),
            over30: owing.filter(r => (r.days || 0) > 30).length,
            today: today && today.data ? n(today.data.total_amount) : null,
            todayCount: today && today.data ? n(today.data.total_receipts) : 0,
          };
          // প্রথমবার বাকি কারো না থাকলে "সবাই" দেখাই — খালি পাতা না দেখিয়ে
          if (this.loading && !owing.length) this.f.tab = 'all';
          if (this.sel) { const r = this.rows.find(x => x.id === this.sel.id); if (r) this.sel = r; }
        } catch (e) { this.error = e.message; }
        this.loading = false;
      },

      count(tab) {
        if (tab === 'due') return this.sum.dueCount;
        if (tab === 'advance') return this.sum.advanceCount;
        return this.rows.length;
      },
      get shown() {
        const q = this.f.q.trim().toLowerCase();
        let out = this.rows.filter(r => {
          if (this.f.tab === 'due' && !(r.due > 0)) return false;
          if (this.f.tab === 'advance' && !(r.advance > 0)) return false;
          return !q || r.name.toLowerCase().includes(q) || r.phone.includes(q) || r.client_no.toLowerCase().includes(q);
        });
        const s = this.f.sort;
        out = out.slice().sort((a, b) => {
          if (s === 'name') return a.name.localeCompare(b.name, BN ? 'bn' : 'en');
          if (s === 'age') return (b.days || -1) - (a.days || -1) || b.due - a.due;
          return (b.due - a.due) || (b.advance - a.advance) || a.name.localeCompare(b.name, 'bn');
        });
        return out;
      },
      get shownDue() { return round2(this.shown.reduce((s, r) => s + r.due, 0)); },
      get shownAdvance() { return round2(this.shown.reduce((s, r) => s + r.advance, 0)); },

      // ───────── একজনের খাতা ─────────
      open(r) {
        this.sel = r;
        this.loadLedger();
        if (window.matchMedia('(min-width: 1101px)').matches) window.scrollTo({ top: 0, behavior: 'smooth' });
        try { const u = new URL(location.href); u.searchParams.set('c', r.id); history.replaceState(null, '', u); } catch (e) { /* ignore */ }
      },
      shut() {
        this.sel = null;
        try { const u = new URL(location.href); u.searchParams.delete('c'); history.replaceState(null, '', u); } catch (e) { /* ignore */ }
      },
      escape() {
        if (this.delDue) this.delDue = null;
        else if (this.due.open) this.due.open = false;
        else if (this.pay.open) this.pay.open = false;
        else if (this.nc.open) this.nc.open = false;
        else if (this.sel) this.shut();
      },
      async loadLedger() {
        if (!this.sel || !this.perms.ledger) return;
        const id = ++this._lreq, cid = this.sel.id;
        this.ledger = { rows: [], loading: true, error: '', totDebit: 0, totCredit: 0 };
        try {
          const [r, dl] = await Promise.all([
            App.api('/api/reports/customer-ledger/', { query: { customer: cid, start: '2000-01-01', end: this.todayIso, page_size: 2000 } }),
            App.api('/api/customer-dues/', { query: { customer: cid } }).catch(() => null),
          ]);
          if (id !== this._lreq) return;
          this.dueMap = Object.fromEntries(((dl && dl.data) || []).map(d => [d.entry_no, d]));
          const rep = r.data && r.data.report;
          const rows = (Array.isArray(rep) ? rep : ((rep && rep.results) || []))
            .filter(e => e.type !== 'Opening' || n(e.due) !== 0)
            .map(e => ({ ...e, debit: n(e.debit), credit: n(e.credit), due: n(e.due) }));
          this.ledger = {
            rows, loading: false, error: '',
            totDebit: round2(rows.reduce((s, e) => s + e.debit, 0)),
            totCredit: round2(rows.reduce((s, e) => s + e.credit, 0)),
          };
        } catch (e) {
          if (id !== this._lreq) return;
          this.ledger = { rows: [], loading: false, error: e.message, totDebit: 0, totCredit: 0 };
        }
      },
      // নতুন লেনদেন আগে, দিন ধরে ভাগ করা
      get ledgerGroups() {
        const groups = [];
        const byDate = {};
        this.ledger.rows.slice().reverse().forEach(e => {
          const d = String(e.date).slice(0, 10);
          if (!byDate[d]) { byDate[d] = { date: d, items: [] }; groups.push(byDate[d]); }
          byDate[d].items.push(e);
        });
        return groups;
      },
      entryTitle(e) {
        if (e.type === 'Sale') return L('Sale', 'বিক্রি');
        if (e.type === 'Return') return L('Goods returned', 'পণ্য ফেরত');
        if (e.type === 'Opening') return L('Brought forward', 'আগের জের');
        if (e.type === 'Due') return /opening/i.test(e.particular || '') ? L('Old khata due', 'পুরনো খাতার বাকি') : L('Gave on credit', 'বাকি দিলাম');
        if (/counter/i.test(e.details || '')) return L('Paid at the counter', 'বিক্রির সময় পেলাম');
        if (/advance/i.test(e.details || '')) return L('Advance received', 'অগ্রিম পেলাম');
        return L('Payment received', 'টাকা পেলাম');
      },
      methodName(m) {
        const k = String(m || '').toLowerCase();
        if (k.startsWith('cash')) return L('Cash', 'ক্যাশ');
        if (k.startsWith('bank')) return L('Bank', 'ব্যাংক');
        if (k.startsWith('mobile')) return L('Mobile banking', 'মোবাইল ব্যাংকিং');
        return m;
      },

      // ───────── তাগাদা ─────────
      remindText(r) {
        if (!r) return '';
        if (r.message) return r.message;
        return `আসসালামু আলাইকুম ${r.name}, ${this.shop.name || 'আমাদের দোকান'} থেকে জানাচ্ছি — আপনার কাছে মোট ৳${bnNum.format(r.due)} বাকি আছে। সুবিধামতো সময়ে পরিশোধ করার অনুরোধ রইল। ধন্যবাদ।`;
      },
      waUrl(r) { const p = intlPhone(r && r.phone); return p ? 'https://wa.me/' + p + '?text=' + encodeURIComponent(this.remindText(r)) : ''; },
      smsUrl(r) { const p = intlPhone(r && r.phone); return p ? 'sms:+' + p + '?&body=' + encodeURIComponent(this.remindText(r)) : ''; },
      markSent(r) { this.sent[r.id] = Date.now(); store.set(SENT_KEY, JSON.stringify(this.sent)); },
      sentText(r) {
        const t = r && this.sent[r.id];
        if (!t) return '';
        const d = Math.floor((Date.now() - t) / DAY);
        if (d <= 0) return L('✓ Reminded today', '✓ আজ তাগাদা দেওয়া হয়েছে');
        if (d === 1) return L('✓ Reminded yesterday', '✓ গতকাল তাগাদা দেওয়া হয়েছে');
        return L('✓ Reminded ' + intFmt.format(d) + ' days ago', '✓ ' + intFmt.format(d) + ' দিন আগে তাগাদা দেওয়া হয়েছে');
      },
      async copy(text) {
        try { await navigator.clipboard.writeText(text); this.say(L('Message copied', 'বার্তা কপি হয়েছে')); }
        catch (e) {
          const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select();
          try { document.execCommand('copy'); this.say(L('Message copied', 'বার্তা কপি হয়েছে')); } catch (e2) { this.say(L('Could not copy', 'কপি করা যায়নি')); }
          ta.remove();
        }
      },

      // ───────── টাকা পেলাম ─────────
      get customerOptions() {
        return this.rows.slice().sort((a, b) => b.due - a.due || a.name.localeCompare(b.name, 'bn'))
          .map(r => ({ value: String(r.id), label: r.name, sub: r.due > 0 ? L('Due ', 'বাকি ') + this.tk(r.due) : (r.phone || '') }));
      },
      get payCustomer() { return this.rows.find(r => String(r.id) === String(this.pay.cid)) || null; },
      get payAccounts() { return this.accounts.filter(a => String(a.ac_type || '').toLowerCase() === this.pay.method.toLowerCase()); },
      get payNum() { const v = parseFloat(String(this.pay.amount).replace(/[,\s]/g, '')); return isFinite(v) ? round2(v) : 0; },
      get quickAmounts() {
        const c = this.payCustomer;
        if (!c || !(c.due > 0)) return [];
        return [100, 500, 1000, 2000, 5000].filter(v => v < c.due).slice(-3);
      },
      // backend এর একই নিয়ম: আগে পুরনো মেমোর বাকি শোধ, বাড়তি টাকা অগ্রিম
      get payPlan() {
        const c = this.payCustomer, a = this.payNum;
        if (!c || a <= 0) return { text: '', cls: '' };
        if (a < c.due) return { text: L('Still due after this: ', 'জমার পরে বাকি থাকবে ') + this.tk(round2(c.due - a)), cls: 'is-left' };
        if (a === c.due) return { text: L('The whole due gets paid off ✓', 'পুরো বাকি শোধ হয়ে যাবে ✓'), cls: 'is-clear' };
        const extra = this.tk(round2(a - c.due));
        return { text: L((c.due > 0 ? 'Due is paid off and ' : '') + extra + ' is kept as advance',
                         (c.due > 0 ? 'বাকি শোধ হবে, আর ' : '') + extra + ' অগ্রিম হিসেবে জমা থাকবে'), cls: 'is-adv' };
      },
      pickAccount() {
        const list = this.payAccounts;
        if (!list.some(a => String(a.id) === this.pay.account)) this.pay.account = list.length ? String(list[0].id) : '';
      },
      openPay(r) {
        if (!this.perms.collect) return;
        this.pay = { open: true, cid: r ? String(r.id) : '', lockCustomer: !!r, amount: '', method: 'Cash', account: '',
          date: this.todayIso, note: '', saving: false, error: '', err: {}, done: null };
        this.pickAccount();
        this.$nextTick(() => { if (r && this.$refs.amt) this.$refs.amt.focus(); });
      },
      payDateTime() {
        if (this.pay.date === this.todayIso) {
          const d = new Date();
          return `${this.pay.date}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
        }
        return `${this.pay.date}T12:00:00`;
      },
      async savePay() {
        const p = this.pay, e = {};
        if (!p.cid) e.amount = L('Pick the customer first.', 'আগে কাস্টমার বাছুন।');
        else if (!(this.payNum > 0)) e.amount = L('Enter how much you got.', 'কত টাকা পেলেন লিখুন।');
        if (!p.account) e.account = this.payAccounts.length || !this.accounts.length
          ? L('Pick the account the money goes into.', 'কোন একাউন্টে জমা হবে বাছুন।')
          : L('There is no ' + p.method + ' account — add one in Accounts first.', 'কোনো ' + p.method + ' একাউন্ট নেই — আগে Accounts এ একটা খুলুন।');
        if (!p.date || p.date > this.todayIso) e.amount = e.amount || L('The date cannot be in the future.', 'ভবিষ্যতের তারিখ দেওয়া যাবে না।');
        p.err = e;
        if (Object.keys(e).length || p.saving) return;
        p.saving = true; p.error = '';
        const c = this.payCustomer;
        const amount = this.payNum;
        try {
          const r = await App.api('/api/money-receipts/', {
            method: 'POST',
            headers: { 'X-Idempotency-Key': 'web-' + Date.now() + '-' + Math.random().toString(36).slice(2) },
            body: {
              customer_id: Number(p.cid), amount: amount.toFixed(2), payment_date: this.payDateTime(),
              payment_method: p.method, account_id: Number(p.account), seller_id: Number(this.me.id),
              remark: (p.note || '').trim() || 'Baki Khata',
            },
          });
          const left = round2(Math.max(0, c.due - amount));
          const adv = round2(Math.max(0, amount - c.due));
          const phone = intlPhone(c.phone);
          const msg = `আসসালামু আলাইকুম ${c.name}, ${this.shop.name || 'আমাদের দোকান'} থেকে আপনার ৳${bnNum.format(amount)} পেয়েছি। ধন্যবাদ!` +
            (left > 0 ? ` এখন বাকি আছে ৳${bnNum.format(left)}।` : ' আপনার সব বাকি শোধ হয়েছে।');
          p.done = { id: r.data && r.data.id, mr: r.data && (r.data.mr_no || r.data.receipt_no), amount, left, adv, name: c.name,
            wa: phone ? 'https://wa.me/' + phone + '?text=' + encodeURIComponent(msg) : '' };
          await this.load();
          if (this.sel && String(this.sel.id) === String(p.cid)) this.loadLedger();
        } catch (err) {
          p.error = this.explain(err);
        }
        p.saving = false;
      },
      explain(e) {
        if (/phone.*(already )?exist/i.test(e.message || '')) return L('A customer with this phone number already exists — search the list.', 'এই ফোন নম্বরে আগে থেকেই একজন কাস্টমার আছে — তালিকায় খুঁজে দেখুন।');
        if (e.status === 0) return L('Cannot reach the server — check your internet.', 'সার্ভারে পৌঁছানো যাচ্ছে না — ইন্টারনেট সংযোগ দেখুন।');
        const d = e.data && e.data.data;
        if (d && typeof d === 'object') {
          const first = Object.entries(d)[0];
          if (first) { const v = first[1]; return Array.isArray(v) ? String(v[0]) : (typeof v === 'string' ? v : e.message); }
        }
        return e.message;
      },

      // ───────── বাকি দিলাম / পুরনো খাতার বাকি ─────────
      num(v) { const x = parseFloat(String(v || '').replace(/[,\s]/g, '')); return isFinite(x) ? round2(x) : 0; },
      get dueCustomer() { return this.rows.find(r => String(r.id) === String(this.due.cid)) || null; },
      get dueNum() { return this.num(this.due.amount); },
      get dueAfter() {
        const c = this.dueCustomer, a = this.dueNum;
        if (!c) return a;
        return round2(c.due > 0 ? c.due + a : Math.max(0, a - c.advance));
      },
      openDue(r, kind) {
        if (!this.perms.due_create || !r) return;
        this.due = { open: true, cid: String(r.id), kind: kind || 'credit', amount: '', date: this.todayIso, note: '', saving: false, error: '', err: {} };
        this.$nextTick(() => this.$refs.dueAmt && this.$refs.dueAmt.focus());
      },
      async saveDue() {
        const d = this.due, e = {};
        if (!(this.dueNum > 0)) e.amount = L('Enter how much.', 'কত টাকা লিখুন।');
        if (!d.date || d.date > this.todayIso) e.date = L('The date cannot be in the future.', 'ভবিষ্যতের তারিখ দেওয়া যাবে না।');
        d.err = e;
        if (Object.keys(e).length || d.saving) return;
        d.saving = true; d.error = '';
        try {
          const r = await App.api('/api/customer-dues/', {
            method: 'POST',
            headers: { 'X-Idempotency-Key': 'web-due-' + Date.now() + '-' + Math.random().toString(36).slice(2) },
            body: { customer_id: Number(d.cid), amount: this.dueNum.toFixed(2), kind: d.kind, entry_date: d.date, note: (d.note || '').trim() },
          });
          d.open = false;
          this.say(L((r.data && r.data.entry_no) + ' saved — ' + this.tk(this.dueNum) + ' added to the due', (r.data && r.data.entry_no) + ' সেভ হয়েছে — বাকিতে ' + this.tk(this.dueNum) + ' যোগ হলো'));
          await this.load();
          if (this.sel && String(this.sel.id) === String(d.cid)) this.loadLedger();
        } catch (err) { d.error = this.explain(err); }
        d.saving = false;
      },
      dueCanDelete(e) { const m = this.dueMap[e.voucher_no]; return !!(m && m.can_delete); },
      askDelDue(e) { this.delDue = e; },
      async doDelDue() {
        const e = this.delDue, m = e && this.dueMap[e.voucher_no];
        this.delDue = null;
        if (!m) return;
        try {
          await App.api('/api/customer-dues/' + m.id + '/', { method: 'DELETE' });
          this.say(L(e.voucher_no + ' deleted', e.voucher_no + ' মুছে ফেলা হয়েছে'));
          await this.load();
          this.loadLedger();
        } catch (err) { this.say(this.explain(err)); }
      },

      // ───────── নতুন কাস্টমার ─────────
      openNew(q) {
        if (!this.perms.create) return;
        const looksPhone = q && /^[\d+\s-]+$/.test(q);
        this.nc = { open: true, name: looksPhone ? '' : (q || ''), phone: looksPhone ? q : '', address: '', opening: '', saving: false, error: '', err: {} };
        this.$nextTick(() => this.$refs.ncName && this.$refs.ncName.focus());
      },
      async saveNew() {
        const c = this.nc, e = {};
        if (!c.name.trim()) e.name = L('Enter a name.', 'নাম লিখুন।');
        if (c.phone.trim() && !intlPhone(c.phone)) e.phone = L('Enter a valid mobile number (e.g. 017XXXXXXXX).', 'সঠিক মোবাইল নম্বর দিন (যেমন 017XXXXXXXX)।');
        if (String(c.opening || '').trim() && !(this.num(c.opening) > 0)) e.opening = L('Enter a number, or leave it empty.', 'সংখ্যা লিখুন, না হলে ফাঁকা রাখুন।');
        c.err = e;
        if (Object.keys(e).length || c.saving) return;
        c.saving = true; c.error = '';
        try {
          const r = await App.api('/api/customers/', { method: 'POST', body: { name: c.name.trim(), phone: c.phone.trim() || null, address: c.address.trim(), is_active: true } });
          const newId = r.data && r.data.id;
          const open = this.num(c.opening);
          if (newId && open > 0) {
            try {
              await App.api('/api/customer-dues/', { method: 'POST', body: { customer_id: newId, amount: open.toFixed(2), kind: 'opening', note: '' } });
            } catch (err) { this.say(L('Customer added, but the old due was not saved: ', 'কাস্টমার যোগ হয়েছে, কিন্তু পুরনো বাকি সেভ হয়নি: ') + this.explain(err)); }
          }
          c.open = false;
          this.say(L(c.name.trim() + ' added', c.name.trim() + ' যোগ হয়েছে'));
          await this.load();
          const id = r.data && r.data.id;
          const row = this.rows.find(x => x.id === id);
          if (row) { this.f.tab = 'all'; this.f.q = ''; this.open(row); }
        } catch (err) { c.error = this.explain(err); }
        c.saving = false;
      },

      // ───────── দেখানো ─────────
      tk(v) { const x = round2(n(v)); return '৳\u00A0' + numFmt.format(x); },
      bn(v) { return intFmt.format(n(v)); },
      // "৪০ দিন থেকে বাকি" / "Due for 40 days"
      sinceText(d) {
        if (d <= 0) return L('Due since today', 'আজ থেকে বাকি');
        if (d === 1) return L('Due since yesterday', 'গতকাল থেকে বাকি');
        return L('Due for ' + intFmt.format(d) + ' days', intFmt.format(d) + ' দিন থেকে বাকি');
      },
      ageCls(d) { return d > 30 ? 'is-old' : (d > 7 ? 'is-mid' : ''); },
      balCls(r) { return r.due > 0 ? 'is-due' : (r.advance > 0 ? 'is-adv' : 'is-zero'); },
      initial(name) { const s = String(name || '?').trim(); return s ? Array.from(s)[0].toUpperCase() : '?'; },
      hue(name) { let h = 0; for (const ch of String(name || '')) h = (h * 31 + ch.codePointAt(0)) % 360; return h; },
      dayLabel(d) {
        const t = this.todayIso;
        const y = iso(new Date(Date.now() - DAY));
        if (d === t) return L('Today', 'আজ');
        if (d === y) return L('Yesterday', 'গতকাল');
        const [yy, mm, dd] = d.split('-').map(Number);
        return intFmt.format(dd) + ' ' + MONTHS[mm - 1] + (yy !== new Date().getFullYear() ? ' ' + intFmt.format(yy).replace(/,/g, '') : '');
      },
      say(t) { this.toast = t; clearTimeout(this._toast); this._toast = setTimeout(() => { this.toast = ''; }, 2600); },
    };
  };
})();
