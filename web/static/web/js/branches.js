/*
 * শাখা — /api/branches/ (branch_warehouse/views.py)
 * ১টা শাখা থাকলে বোঝানো + "শাখা যোগ করুন"; ২+ হলে কার্ড (আজকের বিক্রি, স্টাফ), এডিট, বন্ধ/চালু।
 */
(function () {
  'use strict';
  const L = (en, bn) => (document.documentElement.dataset.lang === 'en' ? en : bn);
  const taka = (v) => '৳' + Number(v || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 });
  function explain(e) {
    const d = e.data && (e.data.errors || e.data.data);
    if (d && typeof d === 'object' && !Array.isArray(d)) {
      const v = Object.values(d)[0];
      if (v) return Array.isArray(v) ? v[0] : String(v);
    }
    return e.message;
  }

  window.branchPage = function (init) {
    return {
      limit: init.limit, packageUrl: init.package_url, staffUrl: init.staff_url,
      rows: [], loading: true, error: '', current: null,
      formOpen: false, form: {}, fe: {}, formError: '', saving: false,
      closing: null, closeErr: '', toast: '',
      taka, L,
      get active() { return this.rows.filter(b => b.is_active); },
      get closed() { return this.rows.filter(b => !b.is_active); },
      get on() { return this.active.length >= 2; },
      // শাখা না থাকলেও দোকান নিজে ১টা
      get used() { return Math.max(1, this.active.length); },
      get full() { return this.limit > 0 && this.used >= this.limit; },

      init() { this.load(); },
      async load() {
        this.loading = true; this.error = '';
        try {
          const r = await App.api('/api/branches/');
          this.rows = r.data.branches || []; this.current = r.data.current;
        } catch (e) { this.error = e.message; }
        this.loading = false;
      },
      openForm(b) {
        if (!b && this.full) return;
        this.form = b ? { id: b.id, name: b.name, address: b.address, phone: b.phone, is_main: b.is_main }
                      : { id: null, name: '', address: '', phone: '' };
        this.fe = {}; this.formError = ''; this.formOpen = true;
        this.$nextTick(() => this.$refs.bfName && this.$refs.bfName.focus());
      },
      async save() {
        const f = this.form;
        if (!f.name.trim()) { this.fe = { name: L('Enter the branch name.', 'শাখার নাম লিখুন।') }; return; }
        if (this.saving) return;
        this.saving = true; this.formError = '';
        const body = { name: f.name.trim(), address: f.address.trim(), phone: f.phone.trim() };
        try {
          const first = !f.id && this.active.length < 2;
          f.id ? await App.api(`/api/branches/${f.id}/`, { method: 'PATCH', body })
               : await App.api('/api/branches/', { method: 'POST', body });
          this.formOpen = false;
          await this.load();
          if (first) { location.reload(); return; }   // শাখা চালু হলো — ওপরে বাছাই, মেনু সব নতুন করে আসুক
          this.flash(f.id ? L('Branch saved.', 'শাখা সেভ হয়েছে।') : L(`${body.name} added.`, `${body.name} যোগ হয়েছে।`));
        } catch (e) { this.formError = explain(e); }
        this.saving = false;
      },
      askClose(b) { this.closing = b; this.closeErr = ''; },
      async setActive(b, active) {
        try {
          await App.api(`/api/branches/${b.id}/`, { method: 'PATCH', body: { is_active: active } });
          const wasOn = this.on;
          this.closing = null;
          await this.load();
          if (wasOn !== this.on) { location.reload(); return; }
          this.flash(active ? L('Branch reopened.', 'শাখা আবার চালু হয়েছে।') : L('Branch closed.', 'শাখা বন্ধ হয়েছে।'));
        } catch (e) { this.closeErr = explain(e); if (active) this.flash(this.closeErr); }
      },
      async pick(b) {
        try { await App.api('/api/branches/current/', { method: 'POST', body: { branch: b ? b.id : 'all' } }); location.reload(); }
        catch (e) { this.flash(e.message); }
      },
      flash(msg) { this.toast = msg; clearTimeout(this._t); this._t = setTimeout(() => { this.toast = ''; }, 3500); },
    };
  };
})();
