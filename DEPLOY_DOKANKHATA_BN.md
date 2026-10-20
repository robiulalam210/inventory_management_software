# dokankhata.meherinmart.com এ দোকান খাতা বসানো (cPanel)

subdomain আর SSL (https) আগে থেকেই চালু আছে। এখন ফোল্ডারে শুধু `cgi-bin` আর `php.ini` আছে। নিচের ধাপগুলো একবারই করতে হবে।

## ১. কোড আপলোড
- cPanel → File Manager → home এ নতুন ফোল্ডার `dokankhata` বানান।
  - পথ হবে `/home/meherinm/dokankhata`।
  - কেন: subdomain এর public ফোল্ডারে (document root) কোড রাখবেন না। তাহলে কোড আর ডাটাবেস ব্রাউজার থেকে দেখা যাবে।
- `dokan_khata_full.zip` সেখানে আপলোড করুন, তারপর Extract করুন।
  - `manage.py` সরাসরি `dokankhata/` এর ভেতরে থাকতে হবে।

## ২. Python App বানানো
cPanel → **Setup Python App** → **Create Application**:

| ঘর | কী দেবেন |
|---|---|
| Python version | 3.11 বা তার বেশি (Django 5.2 এর জন্য কমপক্ষে 3.10 লাগবে) |
| Application root | `dokankhata` |
| Application URL | `dokankhata.meherinmart.com` |
| Application startup file | `passenger_wsgi.py` |
| Application Entry point | `application` |

**Environment variables** (একই পাতায় "Add Variable"):

| নাম | মান |
|---|---|
| `DJANGO_DEBUG` | `0` |
| `DJANGO_SECRET_KEY` | নিচের কমান্ডে বানানো লম্বা random লেখা |
| `DJANGO_EXTRA_ORIGINS` | (দরকার হলে) অন্য domain, যেমন `https://dokankhata.com` — কমা দিয়ে একাধিক। কোড বদলাতে হয় না |

- কেন `DJANGO_DEBUG=0`:
  - ভুল হলে কোড বা পাসওয়ার্ডের তথ্য পাতায় দেখাবে না।
  - https বাধ্যতামূলক হবে, আর লগইনের cookie নিরাপদ থাকবে।
- কেন নতুন `SECRET_KEY`: পুরনোটা কোডের ভেতরে লেখা। এটা দিয়েই লগইন token সই হয়, তাই প্রতিটা সার্ভারে আলাদা আর গোপন রাখতে হবে।

Create চাপার পর নতুন `passenger_wsgi.py` দিয়ে cPanel যদি আমাদেরটা বদলে দেয়, zip থেকে আমাদেরটা আবার বসিয়ে দিন। আমাদেরটা নিজে থেকেই ফোল্ডার খুঁজে নেয়।

## ৩. Terminal এ কমান্ড
Setup Python App পাতার ওপরে "source …/activate && cd …" কমান্ডটা কপি করে cPanel → **Terminal** এ চালান। তারপর:

```bash
pip install -r requirements.txt
python -c "import secrets; print(secrets.token_urlsafe(50))"   # এই লেখাটা DJANGO_SECRET_KEY তে বসান
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

- `migrate`:
  - নতুন, খালি ডাটাবেস (`db.sqlite3`) তৈরি করে।
  - প্যাকেজগুলোও (Free / Starter …) নিজে থেকে বসায়।
- `collectstatic`: CSS, JS আর ছবি একটা ফোল্ডারে জড়ো করে, যাতে whitenoise সেগুলো দ্রুত দিতে পারে।
- `createsuperuser`: আপনার নিজের প্ল্যাটফর্ম-অ্যাডমিন একাউন্ট বানায়।

এরপর Setup Python App এ **Restart** চাপুন।

## ৩.১ সব ঠিক আছে কি না যাচাই
```bash
python manage.py check --deploy
```
"no issues" দেখালে নিরাপত্তার সব সেটিং ঠিক আছে। SECRET_KEY নিয়ে সতর্কবার্তা এলে বুঝবেন environment variable বসেনি।

## ৩.২ প্রতিদিনের ব্যাকআপ (Cron Job)
cPanel → **Cron Jobs** → Once Per Day (রাত ৩টা) → Command:
```
cd /home/meherinm/dokankhata && /home/meherinm/virtualenv/dokankhata/3.11/bin/python manage.py backup_db
```
- python এর পথ Setup Python App পাতার ওপরের কমান্ডে দেখা যায় (3.11 এর জায়গায় আপনার version)।
- কী হয়:
  - `backups/` ফোল্ডারে তারিখসহ কপি রাখে, যেমন `db-2026-10-20-0300.sqlite3`।
  - সবসময় শেষ ১৪ দিনের কপি থাকে।
  - সার্ভার চালু থাকলেও নিরাপদে কপি হয়।
- মাসে একবার একটা কপি নিজের কম্পিউটারে ডাউনলোড করে রাখুন — সার্ভার নষ্ট হলেও তথ্য থাকবে।

## ৩.৩ কোথাও error হলে
- `logs/error.log`:
  - কোন পাতায়, কখন, কী ভুল হয়েছিল, পুরো বিবরণসহ লেখা থাকে।
  - প্রতিদিন নতুন ফাইল হয়; ১৪ দিনের পুরনোগুলো নিজে মুছে যায়।
- ব্যবহারকারী দেখে সুন্দর বাংলা পাতা (৪০৪ / ৫০০), ভেতরের কোড বা তথ্য দেখে না।

## ৪. পরীক্ষা
- https://dokankhata.meherinmart.com/login/ এ লগইন পাতা আসবে।
- https://dokankhata.meherinmart.com/register/ থেকে একটা নতুন দোকান খুলে দেখুন।
- কিছু ভুল হলে `dokankhata/stderr.log` ফাইলটা দেখুন বা আমাকে পাঠান।

## ৫. মোবাইল অ্যাপ
অ্যাপের `.env` ফাইলে লিখুন:

```
BASE_URL=https://dokankhata.meherinmart.com
```

শেষে `/api` দেবেন না, অ্যাপ নিজেই যোগ করে। এরপর নতুন build করুন।

## পরে আপডেট দিতে
1. শুধু বদলানো ফাইলগুলো (patch zip) আপলোড করুন।
2. Terminal এ `python manage.py migrate` আর `python manage.py collectstatic --noinput` চালান।
3. Restart চাপুন।

## নিরাপত্তা
- `db.sqlite3` এ সব দোকানের তথ্য থাকে। সপ্তাহে অন্তত একবার ডাউনলোড করে ব্যাকআপ রাখুন।
- `settings.py` তে পুরনো MySQL পাসওয়ার্ড comment হিসেবে লেখা আছে।
  - ওই পাসওয়ার্ড অন্য কোথাও ব্যবহার হলে বদলে ফেলুন।
  - comment গুলো মুছে দেওয়াই ভালো।
