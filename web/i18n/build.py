"""
বাংলা অনুবাদের অভিধান তৈরি — web/i18n/bn.tsv → web/static/web/js/i18n-bn.js

bn.tsv এর প্রতিটা লাইন:  English লেখা <TAB> বাংলা লেখা
  • হুবহু লেখা:            Save changes	পরিবর্তন সেভ করুন
  • * দিলে যেকোনো অংশ:     * days left	$1 দিন বাকি      ($1, $2 … = প্রথম, দ্বিতীয় * এর জায়গা)
  • # দিয়ে শুরু লাইন = মন্তব্য

নতুন পেজে ইংরেজি লেখা যোগ হলে bn.tsv এ লাইন যোগ করে চালান:
    python web/i18n/build.py
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / 'bn.tsv'
OUT = HERE.parent / 'static' / 'web' / 'js' / 'i18n-bn.js'

# তারিখের মাস/দিনের নাম — বাক্যের ভেতরেও বদলায় (19 Oct 2026 → 19 অক্টো 2026)
WORDS = {
    'January': 'জানুয়ারি', 'February': 'ফেব্রুয়ারি', 'March': 'মার্চ', 'April': 'এপ্রিল', 'June': 'জুন',
    'July': 'জুলাই', 'August': 'আগস্ট', 'September': 'সেপ্টেম্বর', 'October': 'অক্টোবর', 'November': 'নভেম্বর',
    'December': 'ডিসেম্বর', 'Jan': 'জানু', 'Feb': 'ফেব্রু', 'Mar': 'মার্চ', 'Apr': 'এপ্রি', 'Jun': 'জুন',
    'Jul': 'জুলাই', 'Aug': 'আগ', 'Sep': 'সেপ্টে', 'Sept': 'সেপ্টে', 'Oct': 'অক্টো', 'Nov': 'নভে', 'Dec': 'ডিসে',
    'Monday': 'সোমবার', 'Tuesday': 'মঙ্গলবার', 'Wednesday': 'বুধবার', 'Thursday': 'বৃহস্পতিবার', 'Friday': 'শুক্রবার',
    'Saturday': 'শনিবার', 'Sunday': 'রবিবার', 'Mon': 'সোম', 'Tue': 'মঙ্গল', 'Wed': 'বুধ', 'Thu': 'বৃহঃ', 'Fri': 'শুক্র',
    'Sat': 'শনি', 'Sun': 'রবি', 'AM': 'সকাল', 'PM': 'বিকাল', 'am': 'সকাল', 'pm': 'বিকাল',
}


def main():
    exact, patterns, problems = {}, [], []
    for no, line in enumerate(SRC.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip() or line.startswith('#'):
            continue
        if '\t' not in line:
            problems.append(f'{no}: TAB নেই — {line[:60]}')
            continue
        en, bn = (p.strip() for p in line.split('\t', 1))
        if not en or not bn:
            continue
        stars = en.count('*')
        if stars:
            used = {int(x) for x in re.findall(r'\$(\d)', bn)}
            if any(u > stars for u in used):
                problems.append(f'{no}: {en!r} এ {stars}টা * কিন্তু বাংলায় ${max(used)}')
            rx = '^' + '(.+?)'.join(re.escape(part) for part in en.split('*')) + '$'
            patterns.append([rx, bn, len(en.replace('*', ''))])
        else:
            if en in exact and exact[en] != bn:
                problems.append(f'{no}: {en!r} দুবার, আলাদা অনুবাদ')
            exact[en] = bn
    # লম্বা (বেশি নির্দিষ্ট) pattern আগে পরীক্ষা হবে
    patterns.sort(key=lambda p: -p[2])
    # বাক্যের ভেতরের অংশ (browser এ তৈরি হয়): exact এর দুই-বা-বেশি শব্দের লেখা + নিচের মাস/দিনের নাম
    data = {'exact': exact, 'patterns': [p[:2] for p in patterns], 'words': WORDS}
    frags = [k for k in exact if ' ' in k.strip() and len(k) >= 8] + list(WORDS)
    OUT.write_text('/* স্বয়ংক্রিয়ভাবে তৈরি — web/i18n/bn.tsv বদলে web/i18n/build.py চালান। হাতে বদলাবেন না। */\n'
                   'window.DK_BN = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n', encoding='utf-8')
    print(f'{len(exact)} exact, {len(patterns)} patterns, {len(frags)} fragments → {OUT.name}')
    for p in problems:
        print('  !', p)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
