/*
 * Meherin Mart web — সব module এর সাধারণ JavaScript helper।
 *
 * App.api('/api/...') — একই backend API, browser এর session দিয়ে:
 *   • CSRF token নিজে থেকেই যায় (POST/PATCH/DELETE)
 *   • X-Client-Source: web — audit log এ "Web app" হিসেবে দেখায়
 *   • session শেষ হলে login page এ নিয়ে যায়, ফিরে আসার ঠিকানা সহ
 */
(function () {
  'use strict';

  function cookie(name) {
    const m = document.cookie.match('(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)');
    return m ? decodeURIComponent(m[1]) : null;
  }

  function toLogin() {
    const next = encodeURIComponent(location.pathname + location.search);
    location.href = '/app/login/?expired=1&next=' + next;
  }

  async function api(path, opts) {
    opts = opts || {};
    const method = (opts.method || 'GET').toUpperCase();
    const headers = Object.assign({
      'Accept': 'application/json',
      'X-Client-Source': 'web',
      'X-Requested-With': 'XMLHttpRequest',
    }, opts.headers || {});
    let body = opts.body;
    if (body && !(body instanceof FormData) && typeof body !== 'string') {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(body);
    }
    if (method !== 'GET' && method !== 'HEAD') headers['X-CSRFToken'] = cookie('csrftoken') || '';

    let url = path;
    if (opts.query) {
      const q = new URLSearchParams();
      Object.entries(opts.query).forEach(([k, v]) => { if (v !== null && v !== undefined && v !== '') q.append(k, v); });
      const s = q.toString();
      if (s) url += (url.includes('?') ? '&' : '?') + s;
    }

    let res;
    try {
      res = await fetch(url, { method, headers, body, credentials: 'same-origin' });
    } catch (e) {
      throw new ApiError('Cannot reach the server. Check your internet or network connection.', 0);
    }
    if (res.status === 401 || res.status === 403) {
      // session শেষ (403 এ CSRF/permission ও হতে পারে — তখন বার্তা দেখাই)
      const data = await res.json().catch(() => ({}));
      const msg = (data && (data.detail || data.message)) || '';
      if (res.status === 401 || /credentials|authenticat/i.test(msg)) { toLogin(); return new Promise(() => {}); }
      throw new ApiError(msg || 'You do not have permission to do this.', res.status, data);
    }
    const data = await res.json().catch(() => null);
    if (!res.ok || (data && data.status === false)) {
      const msg = (data && (data.message || data.detail)) || ('Request failed (' + res.status + ')');
      throw new ApiError(msg, res.status, data);
    }
    return data;
  }

  class ApiError extends Error {
    constructor(message, status, data) { super(message); this.status = status; this.data = data; }
  }

  const fmtMoney = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  window.App = {
    api,
    ApiError,
    cookie,
    taka: (v) => '৳ ' + fmtMoney.format(Number(v || 0)),
  };
})();
