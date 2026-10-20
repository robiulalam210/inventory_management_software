/*
 * শাখায় মাল পাঠানো — /api/branches/stock/ (কোন শাখায় কত), /api/products/ (পণ্য), /api/branches/transfers/ (পাঠানো)
 * মোট স্টক বদলায় না; শুধু "যেখান থেকে" কমে, "যেখানে" যোগ হয়।
 */
(function () {
  'use strict';
  const L = (en, bn) => (document.documentElement.dataset.lang === 'en' ? en : bn);
  const n = (v) => { const x = Number(v); return isFinite(x) ? x : 0; };
  const fmt = new Intl.NumberFormat('en-IN');

  window.stockTransfer = function (init) {
    return {
      own: init.own_branch, L,
      branches: [], stock: {}, products: [], history: [],
      from: '', to: '', note: '', q: '', rows: [],
      loading: true, error: '', saving: false, formError: '', toast: '',

      async init() {
        try {
          const [s, p, h] = await Promise.all([
            App.api('/api/branches/stock/'),
            App.api('/api/products/', { query: { no_pagination: 'true', is_active: 'true' } }),
            App.api('/api/branches/transfers/').catch(() => ({ data: [] })),
          ]);
          this.branches = ((s.data && s.data.branches) || []).filter(b => b.is_active);
          this.stock = (s.data && s.data.stock) || {};
          const pd = p.data;
          this.products = Array.isArray(pd) ? pd : ((pd && pd.results) || []);
          this.history = h.data || [];
          const main = this.branches.find(b => b.is_main) || this.branches[0];
          this.from = String(this.own || init.current || (main && main.id) || '');
          const other = this.branches.find(b => String(b.id) !== this.from);
          this.to = other ? String(other.id) : '';
        } catch (e) { this.error = e.message; }
        this.loading = false;
      },
      fmt: (v) => fmt.format(n(v)),
      name(id) { const b = this.branches.find(x => String(x.id) === String(id)); return b ? b.name : ''; },
      have(pid, bid) { return n((this.stock[String(pid)] || {})[String(bid)]); },
      swap() { if (this.own) return; const f = this.from; this.from = this.to; this.to = f; },
      get matches() {
        const q = this.q.trim().toLowerCase();
        if (!q) return [];
        const added = new Set(this.rows.map(r => r.id));
        return this.products.filter(p => !added.has(p.id) && (p.name.toLowerCase().includes(q) || String(p.sku || '').toLowerCase().includes(q))).slice(0, 8);
      },
      add(p, qty) {
        if (this.rows.some(r => r.id === p.id)) return;
        this.rows.push({ id: p.id, name: p.name, alert: n(p.alert_quantity), unit: (p.unit_info && (p.unit_info.code || p.unit_info.name)) || '', qty: qty || 1 });
        this.q = '';
      },
      // "যেখানে" যা কম আছে (সতর্কতার সীমার নিচে) — সব একসাথে যোগ, যতটা "যেখান থেকে" দেওয়া যায়
      addLow() {
        let added = 0;
        for (const p of this.products) {
          const alert = n(p.alert_quantity);
          const toHave = this.have(p.id, this.to), fromHave = this.have(p.id, this.from);
          if (alert > 0 && toHave <= alert && fromHave > 0 && !this.rows.some(r => r.id === p.id)) {
            const want = Math.max(1, alert * 2 - toHave);
            this.add(p, Math.min(want, fromHave));
            added++;
          }
        }
        this.flash(added ? L(`${added} products added`, `${added}টা পণ্য যোগ হলো`) : L('Nothing is low there', 'সেখানে কিছু কম নেই'));
      },
      remove(r) { this.rows = this.rows.filter(x => x !== r); },
      bump(r, d) { r.qty = Math.max(1, n(r.qty) + d); },
      over(r) { return n(r.qty) > this.have(r.id, this.from); },
      get canSend() { return this.from && this.to && this.from !== this.to && this.rows.length && !this.rows.some(r => this.over(r) || !(n(r.qty) > 0)); },
      async send() {
        if (!this.canSend || this.saving) return;
        this.saving = true; this.formError = '';
        try {
          const r = await App.api('/api/branches/transfers/', {
            method: 'POST',
            body: { from_branch: Number(this.from), to_branch: Number(this.to), note: this.note.trim(),
                    items: this.rows.map(x => ({ product_id: x.id, qty: Math.round(n(x.qty)) })) },
          });
          this.flash(r.message || L('Sent.', 'পাঠানো হয়েছে।'));
          this.rows = []; this.note = '';
          await this.init();
        } catch (e) {
          const d = e.data && (e.data.errors || e.data.data);
          this.formError = (d && (d.items || d.branch)) || e.message;
        }
        this.saving = false;
      },
      when(s) { const d = new Date(s); return isNaN(d) ? s : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) + ', ' + d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }); },
      flash(m) { this.toast = m; clearTimeout(this._t); this._t = setTimeout(() => { this.toast = ''; }, 3500); },
    };
  };
})();
