# Google Play তে দোকান খাতা — কেনা (Play Billing) আর আপলোডের পুরো নির্দেশনা

## কী তৈরি হলো, আর কেন

| জায়গা | কীভাবে প্যাকেজ কেনা যায় | কেন |
|---|---|---|
| **Android অ্যাপ (Play Store)** | শুধু **Google Play দিয়ে** (কার্ড, মোবাইল ব্যালেন্স ইত্যাদি — Google যা দেয়) | বাংলাদেশে Google Play এর নিয়ম: অ্যাপের ভেতরে সফটওয়্যারের সাবস্ক্রিপশন বিক্রি করলে Play Billing লাগবে, আর বাইরে টাকা দেওয়ার পথ (WhatsApp, বিকাশ নম্বর) অ্যাপে দেখানো যাবে না |
| **ওয়েবসাইট** (`/package/`) | আগের মতো **WhatsApp / বিকাশ** | Google এর নিয়ম শুধু অ্যাপের ভেতরের জন্য — ওয়েবে যা খুশি |
| **ডেস্কটপ (Windows)** অ্যাপ | আগের মতো WhatsApp / বিকাশ | এটা Play Store দিয়ে যায় না |
| **iOS** (ভবিষ্যতে) | অ্যাপে কেনা নেই — শুধু অবস্থা দেখা | Apple এরও একই রকম নিয়ম |

**যাদের কার্ড নেই:** তারা ওয়েবসাইট বা আপনার ফেসবুক পেজ থেকে WhatsApp এ যোগাযোগ করবেন — আপনি Super Admin থেকে আগের মতো প্যাকেজ চালু করে দেবেন। অ্যাপ নিজে থেকেই সেই প্যাকেজ দেখাবে (এটা Google অনুমতি দেয়: "consumption-only")।
**শুধু একটা জিনিস করবেন না:** Android অ্যাপের ভেতরে বা Play Store এর বিবরণে "WhatsApp এ কিনুন / বিকাশে দিন / ওয়েবে সস্তা" — এমন কিছু লিখবেন না। লিখলে অ্যাপ রিজেক্ট বা সরিয়ে দিতে পারে।

### কেনার পথ (ভেতরে কী হয়)
1. দোকানের মালিক অ্যাপে **আরও → আমার প্যাকেজ → Google Play দিয়ে কিনুন** চাপেন।
2. Google Play এর নিজের পর্দায় টাকা দেন। কেনার সাথে দোকানের পরিচয় (`c<company id>`) Google এর কাছে লেখা থাকে।
3. অ্যাপ purchase token সার্ভারে পাঠায়। **সার্ভার অ্যাপের কথা বিশ্বাস করে না** — নিজে Google কে জিজ্ঞেস করে: কেনাটা আসল কি না, কোন প্যাকেজ, কবে পর্যন্ত, কোন দোকানের। তারপর প্যাকেজ চালু করে আর Google কে "পেয়েছি" (acknowledge) জানায় — ৩ দিনের মধ্যে না জানালে Google টাকা ফেরত দিয়ে দেয়।
4. প্রতি মাসে/বছরে নবায়ন, বাতিল, টাকা ফেরত — Google নিজে সার্ভারে খবর পাঠায় (RTDN), মেয়াদ নিজে থেকে ঠিক হয়।
5. নেট চলে গেলেও ভয় নেই: সার্ভার যাচাই না করা পর্যন্ত অ্যাপ কেনাটা "শেষ" ধরে না, পরের বার খুললে আবার যাচাই হয়। আর Google এর খবর (RTDN) এলেও দোকান খুঁজে প্যাকেজ চালু হয়।

নিরাপত্তা: একটা কেনা একটাই দোকানের — অন্য দোকানে একই token দিয়ে চালু করা যায় না; স্টাফ কিনতে পারেন না, শুধু মালিক/অ্যাডমিন। (পরীক্ষা: `tools/tests/test_play_billing.py`, ৩১টা)

---

## ধাপ ১ — Play Console এ পণ্য (সাবস্ক্রিপশন) বানানো
Play Console → অ্যাপ → **Monetize → Products → Subscriptions → Create subscription**

| Product ID (হুবহু এটাই) | নাম | Base plan |
|---|---|---|
| `dk_starter` | স্টার্টার | `monthly` (1 মাস, auto-renew) আর `yearly` (1 বছর, auto-renew) |
| `dk_standard` | স্ট্যান্ডার্ড | `monthly`, `yearly` |
| `dk_business` | বিজনেস | `monthly`, `yearly` |

- Product ID = `dk_` + Super Admin এর প্যাকেজের **code**। নতুন প্যাকেজ বানালে Play তে একই নিয়মে বানান — কোড বদলাতে হবে না।
- Base plan এর id তে `year` থাকলে অ্যাপ সেটাকে বাৎসরিক ধরে।
- **দাম:** বাংলাদেশের দাম BDT তে দিন। Google সাবস্ক্রিপশনে সাধারণত ১৫% কাটে — চাইলে Play এর দাম একটু বেশি রাখতে পারেন (আলাদা দাম রাখা বৈধ; শুধু অ্যাপে "ওয়েবে সস্তা" লেখা যাবে না)।
- ফ্রি ট্রায়াল **Play এ দেবেন না** — ৩০ দিনের ট্রায়াল আমাদের সার্ভার নিজেই দেয়।
- প্রতিটা base plan **Activate** করুন।

## ধাপ ২ — সার্ভারকে Google এর সাথে কথা বলার অনুমতি (Service account)
1. [Google Cloud Console](https://console.cloud.google.com) → একটা project → **APIs & Services → Library → "Google Play Android Developer API" → Enable**।
2. **IAM & Admin → Service accounts → Create**, নাম যেমন `dokan-khata-billing` → তৈরি হলে **Keys → Add key → JSON** → ফাইলটা নামবে।
3. Play Console → **Users and permissions → Invite new users** → service account এর ইমেইল দিন → অনুমতি: **View financial data** আর **Manage orders and subscriptions** → অ্যাপ বাছুন → Invite।
4. JSON ফাইলটা সার্ভারে **public ফোল্ডারের বাইরে** রাখুন, যেমন `/home/meherinm/keys/play-billing.json` (File Manager এ ফাইলের permission 600)। **এটা গোপন — GitHub বা zip এ দেবেন না।**

## ধাপ ৩ — নবায়ন / বাতিলের খবর (RTDN)
1. Google Cloud → **Pub/Sub → Topics → Create topic**, যেমন `dokan-khata-play`।
2. Topic → **Permissions → Add principal**: `google-play-developer-notifications@system.gserviceaccount.com` → role **Pub/Sub Publisher**।
3. Topic → **Create subscription** → Delivery type **Push** → Endpoint:
   `https://dokankhata.meherinmart.com/api/package/play/rtdn/?secret=<একটা লম্বা গোপন লেখা>`
4. Play Console → **Monetization setup → Real-time developer notifications** → Topic name: `projects/<project-id>/topics/dokan-khata-play` → **Send test notification** (সার্ভার "ignored: not a subscription" লিখে 200 দেবে — মানে পৌঁছেছে)।

## ধাপ ৪ — সার্ভারের সেটিং (cPanel → Setup Python App → Environment variables)
| নাম | মান |
|---|---|
| `PLAY_SERVICE_ACCOUNT_FILE` | `/home/meherinm/keys/play-billing.json` |
| `PLAY_RTDN_SECRET` | ধাপ ৩ এর গোপন লেখা (হুবহু) |
| `PLAY_PACKAGE_NAME` | `com.meherin.meherinMart` (না দিলেও এটাই) |
| `SUPPORT_EMAIL` | গোপনীয়তা নীতি পাতায় দেখানোর ইমেইল |

তারপর Terminal এ:
```bash
pip install -r requirements.txt          # নতুন: cryptography (Google এর সাথে নিরাপদ সই)
python manage.py migrate                 # নতুন টেবিল: PlayPurchase, AccountDeletionRequest
python manage.py collectstatic --noinput
```
**Restart** চাপুন। Cron Jobs এ প্রতিদিন একবার যোগ করুন:
```
cd /home/meherinm/dokankhata && /home/meherinm/virtualenv/dokankhata/3.11/bin/python manage.py purge_deleted_accounts
```
(মোছার অনুরোধের ৭ দিন পর একাউন্ট পুরোপুরি মোছে)

সার্ভারে সেটিং না থাকলে অ্যাপে "এখানে প্যাকেজ এখনো পাওয়া যাচ্ছে না" দেখায় — কিছু ভাঙে না।

## ধাপ ৫ — অ্যাপ বানানো
```bash
flutter pub get          # নতুন: in_app_purchase
flutter analyze
flutter build appbundle --release
```
Play Console এ প্রথমে **Internal testing** এ দিন। **Settings → License testing** এ নিজের Gmail যোগ করুন — তখন কেনায় আসল টাকা কাটে না, আর সাবস্ক্রিপশন কয়েক মিনিটে নবায়ন হয় (পরীক্ষা সহজ)।

## ধাপ ৬ — Play Console এর ফর্ম (এগুলো না দিলে রিভিউ আটকে যায়)
- **Privacy policy:** `https://dokankhata.meherinmart.com/privacy/?lang=en`
- **Data safety → Account deletion URL:** `https://dokankhata.meherinmart.com/account/delete/?lang=en`
  (অ্যাপের ভেতরেও আছে: **আরও → একাউন্ট মুছুন**)
- **App access:** "All or some functionality is restricted" → রিভিউয়ারের জন্য একটা টেস্ট দোকানের ইউজারনেম/পাসওয়ার্ড দিন (চালু প্যাকেজ থাকতে হবে, মেয়াদ শেষ হওয়া না)।
- **Data safety (সংক্ষেপে কী লিখবেন):**
  - সংগ্রহ: নাম, ইমেইল, ফোন (একাউন্ট); কেনাকাটার ইতিহাস (প্যাকেজ); অ্যাপের ভেতরের তথ্য (দোকানের হিসাব, কাস্টমারের নাম/ফোন); ডিভাইস আইডি (অফলাইন সিঙ্ক)।
  - উদ্দেশ্য: App functionality, Account management। **বিজ্ঞাপন নয়, বিক্রি নয়।**
  - Encrypted in transit: **Yes** (https)। Users can request deletion: **Yes**।
- **Target audience:** 18+ (ব্যবসার অ্যাপ)। **Ads:** No।

## নতুন পাতা ও API
| ঠিকানা | কাজ |
|---|---|
| `GET /api/package/` | আগের সব + `play` (কোন প্যাকেজ Play তে কেনা যায়, চলমান সাবস্ক্রিপশন) |
| `POST /api/package/play/verify/` | অ্যাপে কেনার পর যাচাই (শুধু মালিক/অ্যাডমিন) |
| `POST /api/package/play/rtdn/?secret=` | Google এর খবর (নবায়ন/বাতিল/টাকা ফেরত) |
| `GET/POST /api/account/delete/` | অ্যাপ থেকে একাউন্ট মোছা (পাসওয়ার্ড দিয়ে) |
| `/privacy/`, `/terms/`, `/account/delete/` | লগইন ছাড়াই খোলা পাতা (বাংলা/English, `?lang=en`) |

## সাথে ঠিক হওয়া একটা পুরনো সমস্যা
কোনো দোকান পুরোপুরি মুছলে (Super Admin থেকে বা একাউন্ট মোছায়) audit log মুছে যাওয়া দোকানের নামে নতুন লাইন লিখত, আর ডাটাবেস পুরো মোছাটাই আটকে দিত। এখন মোছার সময় সেই দোকানের ভেতরের লগ লেখা হয় না (`offline_sync/signals.py`)।
