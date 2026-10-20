# মাল্টি-কোম্পানি ইনভেন্টরি — সেটআপ ও পরীক্ষার গাইড

এই সিস্টেম **মাল্টি-কোম্পানি**: প্রতিটা দোকান (কোম্পানি) আলাদা, মালিক (Super Admin) সবাইকে চালায়।

| কে | কী পারে |
|---|---|
| **Super Admin** (মালিক, কোম্পানি নেই) | Companies: কোম্পানি খোলা, মেয়াদ বাড়ানো, বন্ধ/চালু, Admin এর পাসওয়ার্ড রিসেট · সব কোম্পানির Audit Log · যেকোনো কোম্পানির ভেতরে ঢুকে **শুধু দেখা** (View data) |
| **Admin** (কোম্পানির মালিক) | নিজের কোম্পানির সব কাজ, স্টাফ ও পারমিশন, নিজের Audit Log |
| **Staff** | Admin যতটুকু অনুমতি দেয় |

নতুন কেউ `/register/` (অ্যাপে "Register your company") দিয়ে নিজে কোম্পানি খুললে **৩০ দিনের ফ্রি ট্রায়াল** পায় এবং সে হয় ওই কোম্পানির **Admin** (Super Admin নয়)।

## ১. বসানো (ক্রম মানুন)

1. আগে **ডাটাবেস ও media ফোল্ডারের backup** নিন।
2. প্রজেক্টের ওপর `backend_stock_tools_patch.zip` (বা পুরো zip) extract করুন।
3. `inventory_api/settings.py` এর `INSTALLED_APPS` এ এগুলো আছে কিনা দেখুন:
   ```python
   'payroll',
   'stockops',        # Stock Adjustment / Stocktake / Day Close
   'core.apps.CoreConfig',
   ```
4. কমান্ড (প্রজেক্ট ফোল্ডারে, virtualenv চালু করে):
   ```bash
   pip install -r requirements.txt          # openpyxl, reportlab সহ
   python manage.py makemigrations payroll  # payroll এর migration নেই, এটা তৈরি করে
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py make_superadmin <আপনার username>
   python manage.py backfill_batches --dry-run   # পুরনো স্টকের মেয়াদ: আগে দেখুন
   python manage.py backfill_batches             # ঠিক থাকলে সত্যি চালান
   ```
5. সার্ভার restart দিন (cPanel হলে `tmp/restart.txt` touch করুন), ব্রাউজারে Ctrl+F5।

> নতুন Super Admin বানাতে `python manage.py createsuperuser` চালালেও এখন সঠিক রোল পায়।

## ২. পরীক্ষার তালিকা (কপি ডাটাবেসে আগে)

**Super Admin (ওয়েব)**
- [ ] login করলে বাঁয়ে শুধু **Companies** আর **Audit Log**
- [ ] New company → কোম্পানি + Admin তৈরি হয়
- [ ] Companies এ সারাংশ কার্ড ও Activity কলাম আসে
- [ ] কোম্পানি খুলে **View data** → Admin এর মতো সব দেখা যায়, উপরে "view-only" বার, সেভ করতে গেলে আটকায়, Exit এ ফেরে

**নতুন কোম্পানি (ওয়েব)**
- [ ] `/register/` → কোম্পানি তৈরি, সোজা Dashboard, ট্রায়াল বার্তা
- [ ] Products, Purchase (মেয়াদসহ), Sale, Sale Return
- [ ] সেল মোড (প্যাক/কেজি/গ্রাম): Sold by, Short Sale, প্যাকে দাম × পরিমাণ ঠিক
- [ ] Reports → Excel/PDF Export, Due Reminders, Low Stock সতর্কতা

**অ্যাপ**
- [ ] লগইন পেজের "Register your company" দিয়ে কোম্পানি খোলা
- [ ] Stock Adjustment, Stocktake (শুরু → গোনা → Apply), Expiry Alerts, Day Close
- [ ] Super Admin দিয়ে লগইন → Companies স্ক্রিন, View data, Audit Log

## ৩. জানা সীমা
- ব্যাচ/মেয়াদ শুধু নতুন ক্রয় থেকে তৈরি হয়; পুরনো স্টকের জন্য `backfill_batches` চালান। ক্রয়ের হিসাবে নেই এমন স্টকের (ওপেনিং স্টক) মেয়াদ অজানা থাকে।
- Super Admin কোম্পানির ভেতরে শুধু **দেখতে** পারে, বদলাতে পারে না (ইচ্ছাকৃত)।
- ট্রায়াল শেষ হলে এখন শুধু সতর্কতা দেখায়, লগইন আটকায় না। কোম্পানি বন্ধ (suspended) থাকলে ওয়েব ও অ্যাপ দুটোতেই লগইন আটকায়।
- Django/Flutter এখানে চালিয়ে পরীক্ষা করা যায়নি — উপরের তালিকা ধরে আগে কপিতে দেখুন।
