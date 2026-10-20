/*
 * দোকান খাতা — ভাষা (বাংলা / English)
 *
 * কীভাবে কাজ করে:
 *   • ভাষা থাকে cookie "dk-lang" এ (bn | en)। Server সেটা পড়ে <html data-lang="…"> বসায়।
 *   • English মোডে কিছুই করে না — পেজগুলো ইংরেজিতেই লেখা।
 *   • বাংলা মোডে পর্দার লেখা (text, placeholder, title, aria-label) অভিধান দেখে বাংলা করে —
 *     অভিধান: i18n-bn.js (web/i18n/bn.tsv থেকে তৈরি)। Alpine পরে যা লেখে, MutationObserver সেটাও ধরে।
 *   • যেখানে শুধু টাকা/সংখ্যা/তারিখ, সেখানে অঙ্কও বাংলা (৳ ১,২৩৪)। ইনভয়েস নং / SKU এর মতো
 *     অক্ষর-মেশানো লেখায় অঙ্ক বদলায় না, যাতে খোঁজা ও কপি করা ঠিক থাকে।
 *   • কোনো অংশ অনুবাদ করতে না চাইলে: data-no-i18n
 *
 * ভাষা বদলানো: DK.setLang('bn' | 'en') — cookie বসিয়ে পেজ আবার লোড করে।
 */
(function () {
  'use strict';
  const root = document.documentElement;
  const lang = root.getAttribute('data-lang') || 'en';

  function setLang(l) {
    const v = l === 'bn' ? 'bn' : 'en';
    document.cookie = 'dk-lang=' + v + '; path=/; max-age=31536000; SameSite=Lax';
    try { localStorage.setItem('dk-lang', v); } catch (e) { /* private mode */ }
    location.reload();
  }
  window.DK = { lang, setLang, t: (s) => s, L: (en, bn) => (lang === 'bn' ? bn : en) };

  const D = window.DK_BN;
  if (lang !== 'bn' || !D) { root.classList.remove('dk-i18n-wait'); return; }

  // ───── অভিধান ─────
  const EXACT = new Map(Object.entries(D.exact));
  const PATS = D.patterns.map(([rx, rep]) => [new RegExp(rx), rep]);
  const WORDS = new Map(Object.entries(D.words || {}));
  const fragKeys = [...EXACT.keys()].filter(k => k.trim().includes(' ') && k.length >= 8).concat([...WORDS.keys()])
    .sort((a, b) => b.length - a.length);
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const FRAG_RE = new RegExp('(?<![A-Za-z])(?:' + fragKeys.map(esc).join('|') + ')(?![A-Za-z])', 'g');
  const LATIN = /[A-Za-z]/;
  const BN_DIG = '০১২৩৪৫৬৭৮৯';
  const toBnDigits = (s) => s.replace(/[0-9]/g, (d) => BN_DIG[d]);

  function translate(text) {
    const t = text.trim();
    if (!t) return null;
    let out = null;
    if (LATIN.test(t)) {
      out = EXACT.get(t);
      if (out === undefined) {
        // শেষে ':' বা '.' থাকলে সেটা বাদ দিয়ে দেখা
        const m = t.match(/^(.*?)([:.…])$/);
        if (m && EXACT.has(m[1])) out = EXACT.get(m[1]) + (m[2] === '.' ? '।' : m[2]);
      }
      if (out === undefined) {
        for (const [re, rep] of PATS) {
          const m = t.match(re);
          if (m) {
            out = rep.replace(/\$(\d)/g, (_, i) => { const g = (m[+i] || '').trim(); return EXACT.get(g) || g.replace(FRAG_RE, (f) => EXACT.get(f) || WORDS.get(f) || f); });
            break;
          }
        }
      }
      if (out === undefined) {
        const r = t.replace(FRAG_RE, (f) => EXACT.get(f) || WORDS.get(f) || f);
        out = r !== t ? r : t;
      }
    } else {
      out = t;
    }
    // শুধু সংখ্যা/টাকা/তারিখ (কোনো ইংরেজি অক্ষর নেই) হলে অঙ্ক বাংলা
    if (!LATIN.test(out) && /[0-9]/.test(out)) out = toBnDigits(out);
    if (out === t) return null;
    return text.replace(t, out);
  }

  const SKIP = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'CODE', 'KBD', 'PRE', 'NOSCRIPT', 'TEMPLATE', 'svg', 'SVG']);
  const ATTRS = ['placeholder', 'title', 'aria-label'];
  function skipped(el) {
    for (let e = el; e && e !== root; e = e.parentNode) {
      if (e.nodeType !== 1) continue;
      if (SKIP.has(e.tagName) || e.isContentEditable || e.hasAttribute('data-no-i18n')) return true;
    }
    return false;
  }
  function doText(node) {
    if (!node.nodeValue || skipped(node.parentNode)) return;
    const r = translate(node.nodeValue);
    if (r !== null && r !== node.nodeValue) node.nodeValue = r;
  }
  function doAttrs(el) {
    for (const a of ATTRS) {
      const v = el.getAttribute(a);
      if (v) { const r = translate(v); if (r !== null && r !== v) el.setAttribute(a, r); }
    }
    if (el.tagName === 'INPUT' && (el.type === 'submit' || el.type === 'button') && el.value) {
      const r = translate(el.value); if (r !== null) el.value = r;
    }
  }
  function walk(rootNode) {
    if (rootNode.nodeType === 3) { doText(rootNode); return; }
    if (rootNode.nodeType !== 1) return;
    if (rootNode.tagName === 'TEXTAREA') { doAttrs(rootNode); return; }
    if (skipped(rootNode)) return;
    doAttrs(rootNode);
    const tw = document.createTreeWalker(rootNode, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode(n) {
        if (n.nodeType === 1 && n.tagName === 'TEXTAREA') { doAttrs(n); return NodeFilter.FILTER_REJECT; } // লেখা নয়, শুধু placeholder
        if (n.nodeType === 1 && (SKIP.has(n.tagName) || n.hasAttribute('data-no-i18n'))) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    let n;
    while ((n = tw.nextNode())) { if (n.nodeType === 3) doText(n); else doAttrs(n); }
  }
  function doTitle() {
    const parts = document.title.split(' — ');
    const r = parts.map(p => translate(p) || p).join(' — ');
    if (r !== document.title) document.title = r;
  }

  // ───── Alpine পরে যা বদলায় ─────
  const pending = new Set();
  let scheduled = false;
  function flush() {
    scheduled = false;
    for (const n of pending) { if (n.isConnected) walk(n); }
    pending.clear();
  }
  const mo = new MutationObserver((list) => {
    for (const m of list) {
      if (m.type === 'characterData') pending.add(m.target);
      else if (m.type === 'attributes') pending.add(m.target);
      else m.addedNodes.forEach(n => pending.add(n));
    }
    if (!scheduled) { scheduled = true; queueMicrotask(flush); }
  });

  function start() {
    walk(document.body);
    doTitle();
    root.classList.remove('dk-i18n-wait');
    mo.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
    new MutationObserver(doTitle).observe(document.querySelector('title') || document.head, { childList: true, subtree: true, characterData: true });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
  // কোনো কারণে আটকে গেলেও পেজ লুকিয়ে থাকবে না
  setTimeout(() => root.classList.remove('dk-i18n-wait'), 800);
  window.DK.t = (s) => translate(String(s)) || String(s);
})();
